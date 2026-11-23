import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from saigen.reconstruction_sources import sources
from saigen.agent_shortcuts import RECONSTRUCTION_PATHS as PATHS
from saigen.workspace import prepare, setup
from saigen.records import RecordError


class ReconstructionSourcesTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        self.analysis = self.root / "previous-project"
        self.analysis.mkdir()
        self.codex_home = self.root / "codex"
        environment = {
            "CODEX_HOME": str(self.codex_home),
            "CODEX_THREAD_ID": "current",
        }
        variables = patch.dict(os.environ, environment)
        variables.start()
        self.addCleanup(variables.stop)
        self.configure()

    def configure(self, *paths):
        (self.workspace / "saigen-workspace.json").write_text(json.dumps({
            "agents": ["codex"],
            "reconstruction": {"directory": str(self.analysis), "sources": list(map(str, paths))},
        }))

    def rollout(self, sequence, cwd, *, archived=False, session_id="past"):
        folder = "archived_sessions" if archived else "sessions/2025/10/01"
        path = self.codex_home / folder / f"rollout-2025-10-01T12-00-{sequence:02}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        header = {
            "type": "session_meta",
            "payload": {"cwd": str(cwd), "id": session_id, "timestamp": "2025-10-01T12:00:00Z"},
        }
        path.write_text(json.dumps(header) + "\n" + '{"private_transcript":"example message"}\n')
        return path

    def test_cli_discovers_only_project_candidates_before_proposals_exist(self):
        active = self.rollout(1, self.analysis)
        archived = self.rollout(2, self.workspace, archived=True)
        self.rollout(3, self.analysis.with_name("previous-project-other"))
        self.rollout(4, self.analysis, session_id="current")
        broken = self.rollout(5, self.analysis)
        broken.write_text('{"type":"response_item"}\n' + active.read_text())
        link = broken.with_name("rollout-2025-10-01T12-00-06.jsonl")
        link.symlink_to(active)
        result = subprocess.run(
            [sys.executable, "-B", "-m", "saigen", "reconstruct", "sources",
             "--project", str(self.workspace)],
            capture_output=True, text=True, check=True,
        )
        output = json.loads(result.stdout)
        self.assertEqual(output["status"], "discovered")
        self.assertEqual(output["directory"], str(self.analysis))
        self.assertEqual([item["path"] for item in output["candidates"]], list(map(str, [archived, active])))
        self.assertEqual(output["candidates"][0]["timestamp"], "2025-10-01T12:00:00+00:00")
        self.assertNotIn("example message", result.stdout)
        self.assertFalse((self.workspace / ".saigen").exists())

    @unittest.skipUnless(shutil.which("git"), "Git required")
    def test_nested_analysis_matches_its_git_root(self):
        repo = self.analysis.parent / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        self.analysis = repo / "analysis"
        self.analysis.mkdir()
        self.configure()
        path = self.rollout(1, repo)
        self.assertEqual([item["path"] for item in sources(self.workspace)["candidates"]], [str(path)])

    def test_configured_paths_take_precedence_without_opening_the_sessions(self):
        missing = self.analysis / "missing.md"
        notes = self.analysis / "notes.md"
        notes.touch()
        self.configure(notes, missing)
        with patch("saigen.reconstruction_sources._DISCOVERY", {
            "codex": lambda paths: self.fail("Discovery should be skipped"),
        }):
            output = sources(self.workspace)
        self.assertEqual(output["status"], "configured")
        self.assertEqual(output["candidates"], [
            {"path": str(notes), "origin": "configured", "available": True},
            {"path": str(missing), "origin": "configured", "available": False},
        ])

    def test_fallback_and_bounded_header_scan(self):
        self.assertEqual(sources(self.workspace, "claude")["status"], "unsupported")
        self.assertEqual(sources(self.workspace)["status"], "unavailable")
        self.rollout(1, self.analysis)
        self.rollout(2, self.analysis.with_name("unrelated"))
        with patch("saigen.reconstruction_sources.MAX_CODEX_HEADERS", 1):
            output = sources(self.workspace)
        self.assertEqual(output["status"], "no-matches")
        self.assertEqual(output["candidates"], [])
        self.assertTrue(output["scanLimited"])

    def test_setup_installs_shortcuts_and_preserves_custom_files(self):
        target = self.root / "fresh"
        setup(target, ["codex", "claude", "opencode", "antigravity"], ".", [])
        for agent, path in PATHS.items():
            generated = (target / path).read_text()
            self.assertIn(f"reconstruct sources --agent {agent}", generated)
            self.assertIn("Confirm the source selection", generated)
        custom = target / PATHS["claude"]
        custom.write_text("Custom command")
        with self.assertRaisesRegex(RecordError, "Existing file differs"):
            prepare(target, ["claude"], ".", [])
        self.assertEqual(custom.read_text(), "Custom command")
