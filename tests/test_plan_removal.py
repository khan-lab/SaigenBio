"""Unused-plan lifecycle and history protection, without executing scientific tools."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from saigen.store import Store, RecordError, Conflict, entity, plan_removal_error
from saigen.server import Server
from saigen.workflows.service import WorkflowService, removal_options
from saigen.workflows.execution import execute


class PlanRemovalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = Store(self.root)
        self.store.init()
        path = self.root / 'input.tsv'
        path.write_text('sample\tcount\nA\t3\n')
        self.parent = self.store.snapshot('Existing data', [path], ident='input')
        self.service = WorkflowService(self.store)
        self.spec = {'schemaVersion': 1, 'engine': {'name': 'test', 'version': '1'},
            'pipeline': {'source': '/synthetic/pipeline', 'revision': 'fixture', 'contentDigest': 'fixture'},
            'configuration': {},
            'inputBindings': [{'name': 'table', 'stateId': 'input', 'artifactId': self.parent['artifactIds'][0]}],
            'stages': [{'key': 'one', 'title': 'First', 'dependsOn': [], 'expectedSummary': 'First table',
                'expectedFiles': ['one.tsv'], 'mapping': {'process': 'ONE'}},
                {'key': 'two', 'title': 'Second', 'dependsOn': ['one'], 'expectedSummary': 'Second table',
                'expectedFiles': ['two.tsv'], 'mapping': {'process': 'TWO'}}]}

    def revision(self):
        return self.store.flow()['revision']

    def plan(self, ident, parents=None):
        return self.store.plan(ident, parents or ['input'], 'Expected result', ident=ident)

    def remove(self, ident, revision=None):
        return self.store.edit([{'op': 'delete_state', 'id': ident}], self.revision() if revision is None else revision)

    def propose(self, spec=None):
        return self.service.propose(spec or self.spec, revision=self.revision())

    def cancel(self, p, **kw):
        return self.service.cancel(p['id'], revision=kw.pop('revision', self.revision()), reason='No longer needed', **kw)

    def test_agent_plan_delete_undo_and_stale_revision(self):
        original = self.plan('unused')
        stale = self.revision() - 1
        with self.assertRaises(Conflict):
            self.remove('unused', stale)
        removed = self.remove('unused')
        self.assertEqual([n['id'] for n in removed['states']], ['input'])
        restored = self.store.undo(removed['revision'], self.revision())
        self.assertEqual(entity(restored, 'states', 'unused'), original)
        self.assertEqual(self.store.events()[-1]['kind'], 'flow.undo')
        self.assertTrue(self.store.events()[-2]['undoable'])

    def test_plan_parent_dependency_and_explicit_batch_removal(self):
        self.plan('parent')
        self.plan('child', ['parent'])
        before = self.store.flow()
        with self.assertRaisesRegex(RecordError, 'depends on this plan'):
            self.remove('parent')
        self.assertEqual(self.store.flow(), before)
        removed = self.store.edit([{'op': 'delete_state', 'id': i} for i in ['child', 'parent']], self.revision())
        restored = self.store.undo(removed['revision'], self.revision())
        self.assertEqual(entity(restored, 'states', 'child')['planParents'], ['parent'])

    def test_undo_rechecks_removed_inputs_and_reused_ids(self):
        self.plan('parent')
        self.plan('child', ['parent'])
        deletion = self.remove('child')['revision']
        self.remove('parent')
        before = self.store.flow()
        with self.assertRaisesRegex(Conflict, 'input was removed'):
            self.store.undo(deletion, self.revision())
        self.assertEqual(self.store.flow(), before)
        self.plan('child')
        with self.assertRaisesRegex(Conflict, 'ID has been reused'):
            self.store.undo(deletion, self.revision())

    def test_manual_dependencies_and_action_undo(self):
        self.store.edit([{'op': 'add_state', 'id': i, 'value': {'title': i}} for i in ['parent', 'child']], self.revision())
        self.store.edit([{'op': 'add_action', 'id': 'link', 'value': {'from': ['parent'], 'to': 'child', 'label': 'Later'}}], self.revision())
        with self.assertRaisesRegex(RecordError, 'depends on this plan'):
            self.remove('parent')
        deleted = self.remove('child')
        self.assertEqual(deleted['actions'], [])
        restored = self.store.undo(deleted['revision'], self.revision())
        self.assertEqual(restored['actions'][0]['id'], 'link')
        removed_link = self.store.edit([{'op': 'delete_action', 'id': 'link'}], self.revision())
        self.remove('parent')
        with self.assertRaisesRegex(Conflict, 'connected state was removed'):
            self.store.undo(removed_link['revision'], self.revision())

    def test_legacy_missing_plan_parent_does_not_block_unrelated_edits(self):
        self.plan('legacy')
        def fixture(flow):
            entity(flow, 'states', 'legacy')['planParents'] = ['removed-by-older-release']
            return {}, None
        self.store.update('fixture', 'Test', fixture)
        self.store.edit([{'op': 'edit_state', 'id': 'input', 'changes': {'note': 'Still editable'}}], self.revision())
        deletion = self.remove('legacy')['revision']
        with self.assertRaisesRegex(Conflict, 'input was removed'):
            self.store.undo(deletion, self.revision())

    def test_recorded_statuses_and_artifact_evidence_are_protected(self):
        self.plan('protected')
        for status in ['running', 'completed', 'failed', 'cancelled', 'unknown', 'imported', 'saved']:
            self.store.update('fixture', 'Test', lambda f: (entity(f, 'states', 'protected').update(status=status), None))
            with self.subTest(status=status), self.assertRaisesRegex(RecordError, 'history cannot be deleted'):
                self.remove('protected')
        def evidence(flow):
            entity(flow, 'states', 'protected').update(status='planned', artifactIds=self.parent['artifactIds'])
            return {}, None
        self.store.update('fixture', 'Test', evidence)
        with self.assertRaisesRegex(RecordError, 'artifact evidence'):
            self.remove('protected')

    def test_workflow_cancellation_archives_stages_and_preserves_approval(self):
        p = self.propose()
        approved = self.service.approve(p['id'], p['executionDigest'], revision=self.revision())
        before = copy.deepcopy(self.store.flow())
        stale = self.revision() - 1
        with self.assertRaises(Conflict):
            self.cancel(p, revision=stale)
        with self.assertRaisesRegex(RecordError, 'whole unexecuted workflow'):
            self.remove(p['stageNodes']['one'])
        cancelled = self.cancel(p, actor='Researcher')
        for key in ['spec', 'executionDigest', 'stageNodes', 'approval']:
            self.assertEqual(cancelled[key], approved[key])
        self.assertEqual(cancelled['retirement']['states'], before['states'][1:])
        self.assertEqual(cancelled['retirement']['by'], 'Researcher')
        self.assertEqual([n['id'] for n in self.store.flow()['states']], ['input'])
        self.assertEqual(self.store.events()[-1]['kind'], 'workflow.cancelled')
        self.assertFalse(self.store.events()[-1]['undoable'])
        with self.assertRaisesRegex(RecordError, 'already cancelled'):
            self.cancel(p)
        with self.assertRaisesRegex(RecordError, 'State ID belongs'):
            self.store.edit([{'op': 'add_state', 'id': p['stageNodes']['one'], 'value': {'title': 'Reuse'}}], self.revision())

    def test_cancelled_proposal_cannot_approve_register_or_execute(self):
        p = self.propose()
        self.service.approve(p['id'], p['executionDigest'], revision=self.revision())
        self.cancel(p)
        before = self.store.flow()
        with self.assertRaisesRegex(RecordError, 'was cancelled'):
            self.service.approve(p['id'], p['executionDigest'], revision=self.revision())
        with self.assertRaisesRegex(RecordError, 'was cancelled'):
            self.service.register_run(p['id'], p['executionDigest'], 'engine-id', revision=self.revision())
        with patch('saigen.workflows.execution.adapter') as adapter:
            with self.assertRaisesRegex(RecordError, 'was cancelled'):
                execute(self.service, p['id'], self.revision())
            adapter.assert_not_called()
        self.assertEqual(self.store.flow(), before)

    def test_cancellation_protects_external_plans_and_context_references(self):
        p = self.propose()
        self.plan('dependent', [p['stageNodes']['two']])
        before = self.store.flow()
        with self.assertRaisesRegex(RecordError, 'depends on this plan'):
            self.cancel(p)
        self.assertEqual(self.store.flow(), before)
        self.remove('dependent')
        context = copy.deepcopy(self.spec)
        context['contextStateIds'] = [p['stageNodes']['one']]
        other = self.propose(context)
        with self.assertRaisesRegex(RecordError, 'context references'):
            self.cancel(p)
        self.cancel(other)
        # Historical context remains meaningful, even when its proposal is retired.
        with self.assertRaisesRegex(RecordError, 'context references'):
            self.cancel(p)

    def test_proposal_context_blocks_standalone_removal(self):
        self.plan('context')
        spec = copy.deepcopy(self.spec)
        spec['contextStateIds'] = ['context']
        self.propose(spec)
        with self.assertRaisesRegex(RecordError, 'context references'):
            self.remove('context')

    def test_any_registered_run_prevents_cancellation(self):
        p = self.propose()
        self.service.approve(p['id'], p['executionDigest'], revision=self.revision())
        run = self.service.register_run(p['id'], p['executionDigest'], 'synthetic-engine', revision=self.revision())
        for status in ['running', 'completed', 'failed', 'unknown', 'cancelled']:
            def fixture(flow):
                flow['workflows']['runs'][run['id']]['status'] = status
                return {}, None
            self.store.update('fixture', 'Test', fixture)
            with self.subTest(status=status), self.assertRaisesRegex(RecordError, 'recorded attempts'):
                self.cancel(p)
        for ident in p['stageNodes'].values():
            self.assertIsNotNone(plan_removal_error(self.store.flow(), ident))

    def test_cancellation_during_staging_never_launches_engine(self):
        from saigen.workflows.adapters.base import LaunchSpec
        p = self.propose()
        self.service.approve(p['id'], p['executionDigest'], revision=self.revision())
        revision = self.revision()
        owner = self
        class StagingAdapter:
            def prepare(self, proposal):
                return LaunchSpec(('must-not-run',), '/synthetic', ())
            def stage(self, proposal, folder, params, launch):
                (folder / 'pipeline').mkdir()
                (folder / 'pipeline' / 'main.nf').write_text('// synthetic fixture')
                (folder / 'params.json').write_text('{}')
                (folder / 'saigen.config').write_text('// synthetic fixture')
                owner.cancel(p)
                return launch
        with patch('saigen.workflows.execution.adapter', return_value=StagingAdapter()), \
             patch('saigen.workflows.execution.subprocess.Popen') as launch:
            with self.assertRaises(Conflict):
                execute(self.service, p['id'], revision)
            launch.assert_not_called()
        self.assertEqual(self.store.flow()['workflows']['runs'], {})

    def test_cli_removal_and_cancellation(self):
        def cli(*args):
            result = subprocess.run([sys.executable, '-B', '-m', 'saigen', '--project', str(self.root), *args], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)
        self.plan('unused')
        result = cli('remove-plan', 'unused', '--revision', str(self.revision()))
        self.assertEqual([n['id'] for n in result['states']], ['input'])
        p = self.propose()
        cancelled = cli('workflow', 'cancel', p['id'], '--revision', str(self.revision()), '--reason', 'Different approach')
        self.assertEqual(cancelled['retirement']['reason'], 'Different approach')
        self.assertEqual(cli('workflow', 'show', p['id']), cancelled)

    def test_http_capabilities_delete_undo_and_protected_cancellation(self):
        self.plan('unused')
        p = self.propose()
        with Server(('127.0.0.1', 0), self.store) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f'http://127.0.0.1:{server.server_port}'
                def get(path):
                    with urlopen(base + path) as response:
                        return json.load(response)
                def post(path, body, token=None, origin=None):
                    headers = {'Content-Type': 'application/json'}
                    if token: headers['X-Saigen-Token'] = token
                    if origin: headers['Origin'] = origin
                    return urlopen(Request(base + path, data=json.dumps(body).encode(), headers=headers))
                token = get('/api/session')['token']
                flow = get('/api/flow')
                self.assertIsNone(flow['removalOptions']['states']['unused'])
                self.assertIsNone(flow['removalOptions']['proposals'][p['id']])
                self.assertIsNotNone(flow['removalOptions']['states'][p['stageNodes']['one']])
                body = {'revision': self.revision(), 'operations': [{'op': 'delete_state', 'id': 'unused'}]}
                with post('/api/edit', body, token) as response:
                    deleted = json.load(response)
                with post('/api/undo', {'revision': deleted['revision'], 'event': deleted['revision']}, token) as response:
                    self.assertIsNone(json.load(response)['removalOptions']['states']['unused'])
                path = '/api/workflows/' + p['id'] + '/cancel'
                body = {'revision': self.revision(), 'reason': 'Not needed'}
                with self.assertRaises(HTTPError) as missing:
                    post(path, body)
                self.assertEqual(missing.exception.code, 403)
                with self.assertRaises(HTTPError) as foreign:
                    post(path, body, token, 'https://example.invalid')
                self.assertEqual(foreign.exception.code, 403)
                with post(path, body, token) as response:
                    final = json.load(response)
                self.assertNotIn(p['stageNodes']['one'], final['removalOptions']['states'])
                self.assertIn('already cancelled', final['removalOptions']['proposals'][p['id']])
                self.assertNotIn('removalOptions', self.store.flow())
                with self.assertRaises(HTTPError) as stale:
                    post(path, body, token)
                self.assertEqual(stale.exception.code, 409)
            finally:
                server.shutdown()
                thread.join()
