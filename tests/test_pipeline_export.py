import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from saigen.records import Conflict, RecordError
from saigen.runner import run
from saigen.store import Store
from saigen.workflows import export


class PipelineExportTests(unittest.TestCase):
    def setUp(self):
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        self.root = Path(root.name)
        self.store = Store(self.root)
        self.store.init()
        data = self.root / "source.txt"
        data.write_text("example")
        self.store.snapshot("Imported text", [data], ident="source")
        self.script = self.root / "copy.py"
        self.script.write_text("from pathlib import Path\nimport sys\nPath(sys.argv[2]).write_text(Path(sys.argv[1]).read_text())\n")
        for parent, name in (("source", "intermediate"), ("intermediate", "target")):
            aid = next(n["artifactIds"][0] for n in self.store.flow()["states"] if n["id"] == parent)
            result = run(self.store, [parent], name, [sys.executable, str(self.script), "{input:0}", name + ".txt"],
                         inputs=["artifact:" + aid], outputs=[name + ".txt"], ident=name)
            self.assertEqual(result["exitCode"], 0)

    def revision(self):
        return self.store.flow()["revision"]

    def test_selection_review_boundary_and_generation(self):
        original = self.store.flow()
        selection = export.select(self.store, ["target"], self.revision(), "Researcher")
        full = export.propose(self.store, selection["id"], None, [], "nextflow", self.revision(), "Agent")
        self.assertEqual([s["stateId"] for s in full["plan"]["steps"]], ["intermediate", "target"])
        self.assertFalse(full["plan"]["gaps"])
        limited = export.propose(self.store, selection["id"], None, ["intermediate"], "snakemake", self.revision(), "Agent")
        self.assertEqual([s["stateId"] for s in limited["plan"]["steps"]], ["target"])
        input_entry, = limited["plan"]["inputs"]
        self.assertEqual(input_entry["stateId"], "intermediate")
        with self.assertRaises(RecordError):
            export.generate(self.store, limited["id"], self.revision(), "Agent")
        with self.assertRaises(RecordError):
            export.approve(self.store, limited["id"], full["digest"], "agent-1", "Researcher", False, self.revision(), "Agent")
        with self.assertRaises(Conflict):
            export.approve(self.store, limited["id"], limited["digest"], "agent-1", "Researcher", False, full["revision"], "Agent")
        approved = export.approve(self.store, limited["id"], limited["digest"], "agent-1", "Researcher", False, self.revision(), "Agent")
        generated = export.generate(self.store, limited["id"], approved["revision"], "Agent")
        bundle = Path(generated["directory"])
        manifest = json.loads((bundle / "manifest.json").read_text())
        self.assertEqual(manifest["approval"]["agentSession"], "agent-1")
        self.assertEqual(manifest["sourceRevision"], limited["sourceRevision"])
        self.assertTrue((bundle / "Snakefile").is_file())
        supplied = self.root / "portable input.txt"
        supplied.write_text("example")
        output = bundle / "results/step_1/target.txt"
        subprocess.run([sys.executable, str(bundle / "bundle/run_step.py"), "step_1", str(supplied), str(output)],
                       check=True, cwd=self.root)
        self.assertEqual(output.read_text(), "example")
        self.assertEqual(self.store.flow()["states"], original["states"])
        self.assertEqual(self.store.flow()["actions"], original["actions"])

    def test_unsupported_step_requires_draft_agreement(self):
        plan = self.store.plan("Future", ["source"], "Some output", ident="future")
        self.assertIsNotNone(plan)
        proposal = export.propose(self.store, None, ["future"], [], "nextflow", self.revision(), "Agent")
        self.assertTrue(proposal["plan"]["gaps"])
        with self.assertRaises(RecordError):
            export.approve(self.store, proposal["id"], proposal["digest"], "agent-1", "Researcher", False, self.revision(), "Agent")
        export.approve(self.store, proposal["id"], proposal["digest"], "agent-1", "Researcher", True, self.revision(), "Agent")
        result = export.generate(self.store, proposal["id"], self.revision(), "Agent")
        self.assertTrue(result["draft"])
        self.assertNotIn("bundle/run_step.py", result["files"])

    def test_supplied_script_is_bound_to_a_new_proposal(self):
        replacement = self.root / "replacement.py"
        replacement.write_text(self.script.read_text())
        proposal = export.propose(self.store, None, ["target"], [], "nextflow", self.revision(), "Agent",
                                  {"target": replacement})
        step = proposal["plan"]["steps"][-1]
        self.assertFalse(proposal["plan"]["gaps"])
        self.assertEqual(step["scripts"][-1]["source"], "newly supplied")
        self.assertEqual(step["argv"][1], "{script:1}")
