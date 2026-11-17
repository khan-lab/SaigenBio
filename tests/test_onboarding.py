import contextlib
import io
import json
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from saigen.onboarding import choose_agents, initialize, saved_port, suggested_port, valid_port, viewer_command, yes_no
from saigen.store import Store, RecordError
from saigen.workspace import setup

REPO = Path(__file__).resolve().parent.parent


class OnboardingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "analysis"
        self.store = Store(self.root)

    def initialize(self, answers=(), **kwargs):
        self.output = io.StringIO()
        replies=iter(answers)
        def reply(prompt):
            if "Bring in an existing analysis?" in prompt:return "n"
            answer=next(replies)
            if isinstance(answer,BaseException):raise answer
            return answer
        with patch("sys.stdin.isatty", return_value=True), \
             patch("sys.stdout.isatty", return_value=True), \
             patch("builtins.input", side_effect=reply), \
             patch("saigen.onboarding.can_select", return_value=False), \
             contextlib.redirect_stdout(self.output):
            # redirect_stdout replaces the stream whose isatty was patched.
            with patch.object(self.output, "isatty", return_value=True):
                return initialize(self.store, **kwargs)

    def test_interview_creates_multiple_agents_and_flexible_policy(self):
        self.assertEqual(self.initialize(["Spatial study", "y", "y", "y", "y", "2", "y", "", "n", "y"]), 0)
        self.assertEqual(self.store.flow()["project"], "Spatial study")
        config = json.loads((self.root / "saigen-workspace.json").read_text())
        self.assertEqual(config["agents"], ["codex", "claude", "opencode", "antigravity"])
        self.assertEqual(config["permissionMode"], "flexible")
        self.assertEqual(config["viewer"], f"http://127.0.0.1:{saved_port(self.store)}/")
        for filename in ("AGENTS.md", "CLAUDE.md", "GEMINI.md"):
            instructions = (self.root / filename).read_text()
            self.assertIn("SaigenBio's own UI implementation", instructions)
            self.assertIn("without separate approval for each edit", instructions)
            self.assertIn("does not grant filesystem or network access", instructions)
        for folder in (".agents", ".claude", ".opencode"):
            self.assertTrue((self.root / folder / "skills/saigen-record/SKILL.md").is_file())
        self.assertEqual(self.store.flow()["states"], [])
        self.assertEqual(self.store.flow()["actions"], [])

    def test_cancel_or_eof_writes_nothing(self):
        self.assertEqual(self.initialize(["", "n", "n", "n", "n", "", "n", "n"]), 0)
        self.assertFalse(self.root.exists())
        self.assertEqual(self.initialize([EOFError()]), 130)
        self.assertFalse(self.root.exists())

    def test_flags_skip_all_questions_and_start_only_when_requested(self):
        port = suggested_port()
        with patch("saigen.server.serve") as serve:
            self.assertEqual(self.initialize(["y"], name="Flag project", agents=["codex"],
                port=port, permission="flexible", ui_development="ask", start_viewer=True), 0)
            serve.assert_called_once_with(self.store, port)
        self.assertNotIn("AI agents:", self.output.getvalue())
        self.assertNotIn("Agent workflow permissions:", self.output.getvalue())

    def test_yes_no_enter_respects_default(self):
        with patch("builtins.input", return_value=""):
            self.assertTrue(yes_no("Continue?"))
            self.assertFalse(yes_no("Continue?", False))

    def test_checkbox_selection_is_used_when_supported(self):
        with patch("saigen.onboarding.can_select", return_value=True), \
             patch("saigen.onboarding.checkboxes", return_value=["codex", "claude"]) as select:
            self.assertEqual(choose_agents(), ["codex", "claude"])
            self.assertEqual(select.call_args.args[0], "AI agents")

    def test_declining_startup_prints_runnable_command_with_port(self):
        import shlex
        self.root = self.root.parent / "analysis with spaces"
        self.store = Store(self.root)
        port = suggested_port()
        with patch("saigen.server.serve") as serve:
            self.initialize(["y"], name="Manual startup", agents=[], port=port,
                            start_viewer=False)
            serve.assert_not_called()
        command = viewer_command(self.store, port)
        self.assertIn(command, self.output.getvalue())
        self.assertEqual(shlex.split(command), ["saigen", "serve", "--project", str(self.store.root), "--port", str(port)])
        self.assertIn("Viewer was not started.", self.output.getvalue())
        self.assertIn("Saved viewer address:", self.output.getvalue())

    def test_startup_instruction_uses_dot_in_the_workspace(self):
        port = suggested_port()
        with patch("saigen.onboarding.Path.cwd", return_value=self.store.root), \
             patch("saigen.server.serve") as serve:
            self.initialize(["y"], name="Local startup", agents=[], port=port,
                            start_viewer=False)
            serve.assert_not_called()
        self.assertIn(f"saigen serve --project . --port {port}", self.output.getvalue())
        self.assertIn("Stay in this workspace", self.output.getvalue())

    def test_existing_project_retains_records_and_settings(self):
        self.initialize(["", "n", "n", "n", "n", "", "n", "y"])
        self.store.snapshot("Evidence", [], ident="input")
        before = (self.root / "saigen-workspace.json").read_bytes()
        port = saved_port(self.store)
        self.initialize([], name="Replacement", agents=["claude"], port=9999, permission="flexible")
        self.assertEqual((self.root / "saigen-workspace.json").read_bytes(), before)
        self.assertEqual(saved_port(self.store), port)
        self.assertEqual(self.store.flow()["states"][0]["id"], "input")
        self.assertEqual(self.store.flow()["project"], self.root.name)

    def test_conflicting_instructions_fail_before_creating_project(self):
        self.root.mkdir()
        (self.root / "CLAUDE.md").write_text("My custom rules\n")
        with self.assertRaises(RecordError):
            self.initialize([], name="Conflict", agents=["codex", "claude"],
                            port=suggested_port(), permission="ask", ui_development="ask", start_viewer=False)
        self.assertFalse(self.store.db.exists())
        self.assertFalse((self.root / "AGENTS.md").exists())
        self.assertEqual((self.root / "CLAUDE.md").read_text(), "My custom rules\n")

    def test_add_agent_retains_existing_settings_and_customizations(self):
        self.initialize(["", "y", "n", "n", "n", "2", "n", "", "n", "y"])
        config = json.loads((self.root / "saigen-workspace.json").read_text())
        # User-maintained configuration keys and CLI paths survive additive setup.
        config["custom"] = "keep me"
        config["cli"] = "/custom/runtime/bin/saigen"
        (self.root / "saigen-workspace.json").write_text(json.dumps(config))
        setup(self.root, ["opencode", "claude"], ".", [])
        updated = json.loads((self.root / "saigen-workspace.json").read_text())
        for key in ("viewer", "cli", "custom", "permissionMode"):
            self.assertEqual(updated[key], config[key])
        self.assertEqual(updated["agents"], ["codex", "opencode", "claude"])
        self.assertIn(".agents/skills/saigen-record", (self.root / "AGENTS.md").read_text())
        self.assertIn(".opencode/skills/saigen-record", (self.root / "AGENTS.md").read_text())
        # Custom instructions are not overwritten to add another agent.
        with (self.root / "AGENTS.md").open("a") as handle:
            handle.write("\nMy local rules.\n")
        before = (self.root / "saigen-workspace.json").read_bytes()
        with self.assertRaises(RecordError):
            setup(self.root, "antigravity", ".", [])
        self.assertEqual((self.root / "saigen-workspace.json").read_bytes(), before)
        self.assertFalse((self.root / "GEMINI.md").exists())

    def test_busy_port_is_not_reused_and_no_service_is_stopped(self):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            busy = listener.getsockname()[1]
            self.assertNotEqual(suggested_port(busy), busy)
            with self.assertRaises(RecordError):
                self.initialize([], name="Busy", agents=[], port=busy,
                                non_interactive=True, start_viewer=False)
            self.assertFalse(self.store.db.exists())
            self.assertEqual(listener.getsockname()[1], busy)

    def test_port_validation(self):
        for value in (0, -1, 65536, "abc", True, 1.5):
            with self.subTest(value=value), self.assertRaises(RecordError):
                valid_port(value)

    def test_noninteractive_cli_never_prompts_and_saves_port(self):
        port = suggested_port()
        result = subprocess.run([sys.executable, "-B", "-m", "saigen", "init", "--project", str(self.root),
            "--name", "CLI study", "--agent", "codex", "--agent", "claude", "--port", str(port),
            "--permissions", "flexible", "--non-interactive"], cwd=REPO, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["workspaceSetup"]["agents"], ["codex", "claude"])
        self.assertEqual(saved_port(self.store), port)

    def test_serve_cli_reuses_saved_port_and_explicit_port_overrides(self):
        from saigen.__main__ import main
        self.initialize(["", "n", "n", "n", "n", "", "n", "y"])
        for extra, expected in (([], saved_port(self.store)), (["--port", "0"], 0)):
            with patch.object(sys, "argv", ["saigen", "serve", "--project", str(self.root)] + extra), \
                 patch("saigen.__main__.serve") as serve:
                self.assertEqual(main(), 0)
                self.assertEqual(serve.call_args.args[1], expected)


if __name__ == "__main__":
    unittest.main()
