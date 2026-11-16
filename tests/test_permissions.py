"""Independent scopes and compatibility of generated workspace instructions."""
import json
import tempfile
import unittest
from pathlib import Path

from saigen.store import RecordError
from saigen.workspace import instruction_files, prepare, setup, write_files


class PermissionTests(unittest.TestCase):
    def test_scopes_are_independent(self):
        for analysis in ('ask', 'flexible'):
            for development in ('ask', 'allow'):
                with self.subTest(analysis=analysis, development=development):
                    with tempfile.TemporaryDirectory() as directory:
                        root, files, config = prepare(directory, ['codex'], '.', [], permission=analysis, ui_development=development)
                        self.assertEqual(config['permissionMode'], analysis)
                        self.assertEqual(config['uiDevelopment'], development)
                        instructions = files['AGENTS.md']
                        self.assertEqual('without separate approval for each edit' in instructions, development == 'allow')
                        self.assertEqual('Ask before starting proposed downloads' in instructions, analysis == 'ask')
                        write_files(root, files)
                        setup(root, 'claude', '.', [])
                        updated = json.loads((root / 'saigen-workspace.json').read_text())
                        self.assertEqual(updated['uiDevelopment'], development)
                        self.assertEqual(updated['permissionMode'], analysis)

    def test_new_setup_defaults_to_asking_for_source_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            _, files, config = prepare(directory, ['codex'], '.', [], permission='flexible')
            self.assertEqual(config['uiDevelopment'], 'ask')
            self.assertNotIn('without separate approval for each edit', files['AGENTS.md'])

    def test_legacy_policy_survives_adding_agent(self):
        for analysis in ('ask', 'flexible'):
            with self.subTest(analysis=analysis), tempfile.TemporaryDirectory() as directory:
                root, files, config = prepare(directory, ['codex'], '.', [], permission=analysis)
                config.pop('uiDevelopment')
                files['saigen-workspace.json'] = json.dumps(config)
                skill = files['.agents/skills/saigen-record/SKILL.md']
                files.update(instruction_files(['codex'], skill, analysis))
                write_files(root, files)
                before = (root / 'AGENTS.md').read_bytes()
                setup(root, 'claude', '.', [])
                self.assertEqual(before, (root / 'AGENTS.md').read_bytes())
                self.assertNotIn('uiDevelopment', json.loads((root / 'saigen-workspace.json').read_text()))
                self.assertEqual('without separate approval for each edit' in (root / 'CLAUDE.md').read_text(), analysis == 'flexible')

    def test_changing_saved_scope_is_rejected_before_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            setup(directory, 'codex', '.', [], permission='flexible', ui_development='ask')
            config = Path(directory) / 'saigen-workspace.json'
            before = config.read_bytes()
            with self.assertRaises(RecordError):
                setup(directory, 'claude', '.', [], ui_development='allow')
            self.assertEqual(config.read_bytes(), before)
            self.assertFalse((Path(directory) / 'CLAUDE.md').exists())
