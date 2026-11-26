import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from saigen.workspace import setup
from saigen.agent_shortcuts import (
    ORGANIZATION_PATHS, PIPELINE_PATHS, RECONSTRUCTION_PATHS, WORKFLOW_DISCOVERY_PATHS,
)

REPO = Path(__file__).resolve().parent.parent
RULES = [
    "/.agents/skills/saigen-record/",
    "/.claude/skills/saigen-record/",
    "/.opencode/skills/saigen-record/",
]


@unittest.skipUnless(shutil.which("git"), "Git required")
class SkillIgnoreTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()

    def git(self, *args, check=True):
        return subprocess.run(
            ["git", "-C", str(self.root), *args], capture_output=True, text=True, check=check
        )

    def test_init_scopes_rules_to_the_nested_workspace(self):
        self.git("init", "-q")
        workspace = self.root / "analysis"
        workspace.mkdir()
        existing = b"# Preserve this comment\r\nprivate-data/"
        (workspace / ".gitignore").write_bytes(existing)
        self.git("add", "analysis/.gitignore")
        result = subprocess.run(
            [sys.executable, "-B", "-m", "saigen", "init", "--project", str(workspace),
             "--non-interactive", "--no-start-viewer", "--agent", "codex",
             "--agent", "antigravity", "--agent", "claude", "--agent", "opencode"],
            cwd=REPO, capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        ignore = (workspace / ".gitignore").read_bytes()
        self.assertTrue(ignore.startswith(existing + b"\r\n"))
        for rule in RULES:
            self.assertEqual(ignore.splitlines().count(rule.encode()), 1)
            folder = "analysis" + rule.rstrip("/")
            for path in (f"{folder}/SKILL.md", f"{folder}/references/example.md"):
                self.assertEqual(self.git("check-ignore", "-q", path).returncode, 0)
        for path in (*RECONSTRUCTION_PATHS.values(), *ORGANIZATION_PATHS.values(), *PIPELINE_PATHS.values()):
            self.assertEqual(self.git("check-ignore", "-q", f"analysis/{path}").returncode, 0)
        for path in WORKFLOW_DISCOVERY_PATHS.values():
            generated = workspace / path
            self.assertIn("Find a published workflow", generated.read_text())
            self.assertEqual(self.git("check-ignore", "-q", f"analysis/{path}").returncode, 0)
        for path in (".agents/skills/saigen-record/SKILL.md",
                     "analysis/.agents/skills/another/SKILL.md",
                     "analysis/AGENTS.md", "analysis/saigen-workspace.json"):
            self.assertEqual(self.git("check-ignore", "-q", path, check=False).returncode, 1)
        previous_shortcut = workspace / WORKFLOW_DISCOVERY_PATHS["codex"]
        previous_shortcut.unlink()
        setup(workspace, "codex", ".", [])
        self.assertIn("Find a published workflow", previous_shortcut.read_text())
        self.assertEqual((workspace / ".gitignore").read_bytes(), ignore)
        self.assertFalse((self.root / ".gitignore").exists())

    def test_setup_preserves_already_tracked_skill_files(self):
        setup(self.root, "claude", ".", [])
        ignore = self.root / ".gitignore"
        self.assertFalse(ignore.exists())
        self.git("init", "-q")
        skill = ".claude/skills/saigen-record/SKILL.md"
        self.git("add", skill)
        setup(self.root, "opencode", ".", [])
        self.assertEqual(self.git("ls-files", skill).stdout.strip(), skill)
        self.assertEqual(ignore.read_text().splitlines(), RULES[1:] + [
            "/" + WORKFLOW_DISCOVERY_PATHS["claude"],
            "/" + ORGANIZATION_PATHS["claude"], "/" + PIPELINE_PATHS["claude"], "/" + RECONSTRUCTION_PATHS["claude"],
            "/" + WORKFLOW_DISCOVERY_PATHS["opencode"],
            "/" + ORGANIZATION_PATHS["opencode"], "/" + PIPELINE_PATHS["opencode"], "/" + RECONSTRUCTION_PATHS["opencode"],
        ])
        self.git("check-ignore", "-q", ".opencode/skills/saigen-record/SKILL.md")
