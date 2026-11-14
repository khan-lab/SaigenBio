import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

from saigen.terminal import color

REPO = Path(__file__).resolve().parent.parent


class ColorTests(unittest.TestCase):
    def test_colors_respect_no_color_and_redirected_output(self):
        with patch("sys.stdin.isatty", return_value=True), patch("sys.stdout.isatty", return_value=True):
            with patch.dict(os.environ, {"TERM": "xterm-256color"}, clear=True):
                self.assertIn("\033[36m", color("Project name"))
            with patch.dict(os.environ, {"TERM": "xterm-256color", "NO_COLOR": "1"}, clear=True):
                self.assertEqual(color("Project name"), "Project name")
            with patch.dict(os.environ, {"TERM": "dumb"}, clear=True):
                self.assertEqual(color("Project name"), "Project name")
        with patch("sys.stdout.isatty", return_value=False):
            self.assertEqual(color("Project name"), "Project name")


@unittest.skipUnless(os.name == "posix", "Checkbox key handling uses a POSIX terminal")
class CheckboxTerminalTests(unittest.TestCase):
    def run_selector(self, keys=None, cancel=False, no_color=False):
        import pty
        import termios
        master, slave = pty.openpty()
        self.addCleanup(os.close, master)
        self.addCleanup(os.close, slave)
        original = termios.tcgetattr(slave)
        code = """import json
from saigen.terminal import checkboxes
try:
    result=checkboxes('AI agents',['codex','claude','opencode','antigravity'])
    print('RESULT='+json.dumps(result),flush=True)
except KeyboardInterrupt:
    print('CANCELLED',flush=True)
"""
        env = os.environ.copy()
        env["TERM"] = "xterm-256color"
        if no_color:
            env["NO_COLOR"] = "1"
        else:
            env.pop("NO_COLOR", None)
        child = subprocess.Popen([sys.executable, "-B", "-c", code], cwd=REPO, env=env,
                                 stdin=slave, stdout=slave, stderr=slave)
        self.addCleanup(lambda: child.poll() is None and child.kill())
        output = b""

        def read_until(marker):
            nonlocal output
            deadline = time.monotonic() + 5
            while marker not in output:
                self.assertLess(time.monotonic(), deadline, output.decode(errors="replace"))
                if select.select([master], [], [], .1)[0]:
                    output += os.read(master, 65536)
        read_until(b"antigravity")
        if cancel:
            child.send_signal(signal.SIGINT)
            read_until(b"CANCELLED")
        else:
            os.write(master, keys)
            read_until(b"RESULT=")
        child.wait(timeout=5)
        while select.select([master], [], [], .05)[0]:
            output += os.read(master, 65536)
        self.assertEqual(child.returncode, 0, output.decode(errors="replace"))
        restored = termios.tcgetattr(slave)
        # Compare persistent settings, including echo/canonical/signals and
        # control characters. lflag can also contain transient pending-input bits.
        self.assertEqual(restored[:3], original[:3])
        modes = termios.ECHO | termios.ICANON | termios.ISIG
        self.assertEqual(restored[3] & modes, original[3] & modes)
        self.assertEqual(restored[4:], original[4:])
        self.assertIn(b"\033[?25h", output)
        text = output.decode(errors="replace")
        if no_color:
            self.assertNotIn("\033[36m", text)
            self.assertNotIn("\033[32m", text)
        return text

    def test_arrows_toggle_multiple_choices_and_deselect(self):
        text = self.run_selector(b" \x1b[B \x1b[B \x1b[A \n")
        self.assertEqual(json.loads(text.split("RESULT=", 1)[1].strip()), ["codex", "opencode"])

    def test_all_none_and_confirm_without_selections(self):
        text = self.run_selector(b"an\n", no_color=True)
        self.assertEqual(json.loads(text.split("RESULT=", 1)[1].strip()), [])

    def test_select_all(self):
        text = self.run_selector(b"a\n")
        self.assertEqual(json.loads(text.split("RESULT=", 1)[1].strip()), ["codex", "claude", "opencode", "antigravity"])

    def test_cancel_restores_terminal(self):
        self.run_selector(cancel=True)


if __name__ == "__main__":
    unittest.main()
