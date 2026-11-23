import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from saigen.agent_shortcuts import ORGANIZATION_PATHS
from saigen.analysis_groups import replace, show
from saigen.records import Conflict, RecordError
from saigen.store import Store
from saigen.workspace import setup


class AnalysisGroupsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.store = Store(self.root)
        self.store.init("Group test")
        source = self.root / "source.tsv"
        source.write_text("sample\tvalue\na\t1\n")
        self.store.snapshot("Shared input", [source], ident="input")
        self.before = self.store.edit([
            {"op": "add_state", "id": "counts", "value": {"title": "Counts", "x": 340}},
            {"op": "add_state", "id": "model", "value": {"title": "Model", "x": 680}},
            {"op": "add_action", "id": "fit", "value": {
                "from": ["input", "counts"], "to": "model", "label": "Fit model", "command": "fit.py",
            }},
        ], self.store.flow()["revision"])
        self.group = {"id": "analysis", "title": "One analysis", "stateIds": ["counts", "model"],
                      "reason": "These results belong to the same dataset."}

    def cli(self, *arguments):
        result = subprocess.run(
            [sys.executable, "-B", "-m", "saigen", "--project", str(self.root), *arguments],
            text=True, capture_output=True, timeout=10, check=True,
        )
        return json.loads(result.stdout)

    def test_save_and_revise_through_cli_without_changing_analysis(self):
        before_events = self.store.events()
        old = self.cli("groups", "show")
        self.assertEqual(old["groups"], [])
        path = self.root / "groups.json"
        path.write_text(json.dumps([self.group]))
        saved = self.cli("groups", "save", "--file", str(path), "--revision", str(old["revision"]))
        self.assertEqual(saved, self.cli("groups", "show"))
        self.assertEqual(saved["groups"], [self.group])
        after = self.store.flow()
        for key in ("states", "actions", "artifacts"):
            self.assertEqual(after[key], self.before[key])
        self.assertEqual(self.store.events()[:-1], before_events)
        self.assertEqual(self.store.events()[-1]["kind"], "canvas.groups.updated")
        edited = {**self.group, "title": "Renamed", "stateIds": ["model"]}
        again = replace(self.store, [edited], saved["revision"], "AI agent")
        self.assertEqual(again["groups"], [edited])
        self.assertEqual(replace(self.store, [], again["revision"], "AI agent")["groups"], [])

    def test_reject_overlaps_missing_states_and_stale_saves_atomically(self):
        rev = self.before["revision"]
        for groups in (
            [self.group, {**self.group, "id": "other", "title": "Other"}],
            [{**self.group, "stateIds": ["missing"]}],
            [{**self.group, "stateIds": ["model", "model"]}],
            [{**self.group, "stateIds": []}],
        ):
            with self.assertRaises(RecordError):
                replace(self.store, groups, rev, "AI agent")
            self.assertEqual(show(self.store), {"revision": rev, "groups": []})
        replace(self.store, [self.group], rev, "AI agent")
        with self.assertRaises(Conflict):
            replace(self.store, [], rev, "AI agent")

    def test_removed_members_do_not_reattach_to_a_reused_state_id(self):
        saved = replace(self.store, [self.group], self.before["revision"], "AI agent")
        after = self.store.edit([{"op": "delete_state", "id": "model"}], saved["revision"])
        self.assertEqual(after["analysisGroups"][0]["stateIds"], ["counts"])
        after = self.store.edit([{"op": "delete_state", "id": "counts"}], after["revision"])
        self.assertEqual(after["analysisGroups"], [])
        restored = self.store.undo(after["revision"], after["revision"])
        self.assertIn("counts", [state["id"] for state in restored["states"]])
        self.assertEqual(restored["analysisGroups"], [])

    def test_nested_groups_allow_variable_depth_and_retire_empty_ancestors(self):
        groups = [
            {"id": "inner", "parentId": "stage", "title": "Modeling", "stateIds": ["model"]},
            {"id": "stage", "parentId": "big", "title": "Phase", "stateIds": []},
            {"id": "big", "title": "Cell analysis", "stateIds": ["counts"]},
            {"id": "shared", "title": "Modeling", "stateIds": ["input"]},
        ]
        rev = self.before["revision"]
        for bad_parent in ("inner", "unknown", "stage"):
            invalid = [{**groups[0], "parentId": bad_parent}, groups[1],
                       {**groups[2], "parentId": "inner"}, groups[3]]
            with self.assertRaises(RecordError):
                replace(self.store, invalid, rev, "AI agent")
        saved = replace(self.store, groups, rev, "AI agent")
        self.assertEqual([g.get("parentId") for g in saved["groups"]], ["stage", "big", None, None])
        after = self.store.edit([{"op": "delete_state", "id": "model"}], saved["revision"])
        self.assertEqual([g["id"] for g in after["analysisGroups"]], ["big", "shared"])

    def test_setup_generates_organization_shortcuts(self):
        workspace = self.root / "agent"
        setup(workspace, list(ORGANIZATION_PATHS), ".", [])
        for agent, path in ORGANIZATION_PATHS.items():
            skill = (workspace / path).read_text()
            self.assertIn("refine the proposal", skill)
            self.assertIn("save it after agreement", skill)
            self.assertIn("saigen-record/SKILL.md", skill)
            self.assertIn("description:", skill)
            if agent == "codex":
                self.assertIn("name: saigen-organize", skill)

    def test_overview_layout_is_saved_and_undone_without_moving_states(self):
        groups = [{"id": "results", "title": "Results", "stateIds": ["model"]}]
        revision = replace(self.store, groups, self.before["revision"], "Agent")["revision"]
        layout = {"scale": .5, "cards": [
            {"id": "input", "x": 64, "y": 65},
            {"id": "group:results", "x": 560, "y": 67},
        ]}
        saved = self.store.edit([{"op": "edit_overview", "layout": layout}], revision)
        self.assertEqual(saved["states"], self.before["states"])
        self.assertEqual(saved["actions"], self.before["actions"])
        self.assertEqual(set(saved["overviewLayouts"]), {"group:results|input"})
        self.assertEqual(self.store.flow()["overviewLayouts"], saved["overviewLayouts"])
        with self.assertRaises(RecordError):
            self.store.edit([{"op": "edit_overview", "layout": {**layout, "cards": [
                {"id": "group:unknown", "x": 12, "y": 40},
            ]}}], saved["revision"])
        undone = self.store.undo(saved["revision"], saved["revision"])
        self.assertNotIn("overviewLayouts", undone)
        self.assertEqual(undone["states"], self.before["states"])
