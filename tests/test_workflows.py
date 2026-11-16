"""Foundation invariants, using synthetic evidence rather than a real workflow engine."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from saigen.store import Store, RecordError, Conflict
from saigen.workflows.service import WorkflowService


class WorkflowTests(unittest.TestCase):
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
            'pipeline': {'source': '/synthetic/pipeline', 'revision': 'fixture', 'contentDigest': 'fixture-digest'},
            'configuration': {'parameters': {'minimum': 2}},
            'inputBindings': [{'name': 'table', 'stateId': 'input', 'artifactId': self.parent['artifactIds'][0]}],
            'stages': [{'key': 'filtered', 'title': 'Filtered data', 'dependsOn': [], 'expectedSummary': 'Filtered table',
                'expectedFiles': ['filtered.tsv'], 'mapping': {'source': 'test-fixture', 'taskSelectors': ['filter']}},
                {'key': 'summary', 'title': 'Summary', 'dependsOn': ['filtered'], 'expectedSummary': 'Summary table',
                'expectedFiles': ['summary.tsv'], 'mapping': {'source': 'test-fixture', 'taskSelectors': ['summarize']}}]}

    def revision(self):
        return self.store.flow()['revision']

    def propose(self, spec=None):
        return self.service.propose(spec or self.spec, revision=self.revision())

    def approve(self, proposal):
        return self.service.approve(proposal['id'], proposal['executionDigest'], revision=self.revision())

    def observe_run(self, proposal, engine_id='synthetic-run'):
        return self.service.register_run(proposal['id'], proposal['executionDigest'], engine_id, revision=self.revision())

    def test_atomic_publication_and_legacy_flow(self):
        self.assertNotIn('workflows', self.store.flow())
        before = self.revision()
        p = self.propose()
        flow = self.store.flow()
        self.assertEqual(flow['revision'], before + 1)
        self.assertEqual(len(flow['states']), 3)
        self.assertEqual(flow['actions'], [])
        node = next(n for n in flow['states'] if n['id'] == p['stageNodes']['summary'])
        self.assertEqual(node['planParents'], [p['stageNodes']['filtered']])
        self.assertEqual(node['status'], 'planned')
        self.assertIsNone(p['approval'])
        self.assertEqual(self.spec['stages'][0]['title'], 'Filtered data')

    def test_invalid_proposals_do_not_partially_publish(self):
        for mutate in (lambda s: s['stages'][1].update(dependsOn=['missing']),
                       lambda s: s['inputBindings'][0].update(artifactId='missing'),
                       lambda s: s.update(contextStateIds=['missing']),
                       lambda s: s['stages'][1].update(dependsOn=[{}])):
            spec = copy.deepcopy(self.spec)
            mutate(spec)
            before = self.store.flow()
            with self.assertRaises(RecordError):
                self.propose(spec)
            self.assertEqual(self.store.flow(), before)

    def test_stale_revision_rejects_without_writes(self):
        with self.assertRaises(Conflict):
            self.service.propose(self.spec, revision=0)
        self.assertNotIn('workflows', self.store.flow())

    def test_approval_required_and_configuration_bound(self):
        p = self.propose()
        with self.assertRaises(RecordError):
            self.observe_run(p)
        with self.assertRaises(RecordError):
            self.service.approve(p['id'], 'wrong', revision=self.revision())
        self.approve(p)
        self.assertEqual(self.store.flow()['workflows']['runs'], {})
        self.spec['configuration']['parameters']['minimum'] = 10
        replacement = self.propose()
        self.assertNotEqual(replacement['executionDigest'], p['executionDigest'])
        with self.assertRaises(RecordError):
            self.observe_run(replacement)
        self.assertIsNone(self.service.show(replacement['id'])['approval'])
        self.assertTrue(self.service.show(p['id'])['approval'])

    def test_annotation_and_layout_preserve_approval(self):
        p = self.propose()
        self.approve(p)
        node = p['stageNodes']['filtered']
        self.store.edit([{'op': 'edit_state', 'id': node, 'changes': {'note': 'Review note', 'x': 99}}], self.revision())
        observed = self.observe_run(p)
        self.assertEqual(observed['executionDigest'], p['executionDigest'])
        with self.assertRaises(RecordError):
            self.store.edit([{'op': 'edit_state', 'id': node, 'changes': {'status': 'completed'}}], self.revision())

    def test_evidence_replay_conflict_and_uncertainty(self):
        p = self.propose()
        self.approve(p)
        observed = self.observe_run(p)
        event = {'id': 'task1-running', 'stage': 'filtered', 'attempt': 1,
            'status': 'running', 'source': 'synthetic trace', 'artifactIds': []}
        for _ in range(2):
            result = self.service.reconcile(observed['id'], [event], revision=self.revision())
        self.assertEqual(len(result['events']), 1)
        conflict = {**event, 'status': 'completed'}
        before = self.store.flow()
        with self.assertRaises(RecordError):
            self.service.reconcile(observed['id'], [conflict], revision=self.revision())
        self.assertEqual(self.store.flow(), before)
        observations = [{**event, 'id': f'event-{i}', 'status': status, 'attempt': i+1}
            for i, status in enumerate(['failed', 'cached', 'skipped', 'unknown', 'completed'])]
        result = self.service.reconcile(observed['id'], observations, revision=self.revision())
        self.assertEqual(len(result['events']), 6)
        self.assertTrue(all(n['status'] == 'planned' for n in self.store.flow()['states'][1:]))
        self.assertEqual(len(self.store.flow()['artifacts']), 1)
        second = self.observe_run(p, 'synthetic-retry')
        self.assertNotEqual(second['id'], observed['id'])
        with self.assertRaises(RecordError):
            self.observe_run(p, 'synthetic-retry')


    def test_adapter_contract_with_synthetic_evidence(self):
        from saigen.workflows.adapters.base import EngineInfo, LaunchSpec, EvidenceBatch
        class SyntheticAdapter:
            def discover(self):
                return EngineInfo('test', '1', True, {'execution': False})
            def inspect(self, source, configuration):
                return {'source': source, 'limitations': ['Synthetic fixture only']}
            def prepare(self, proposal):
                return LaunchSpec(('not-an-executable-fixture',), '/synthetic', ())
            def collect(self, run_reference, cursor):
                return EvidenceBatch(({'id': 'synthetic-task-1', 'stage': 'filtered', 'attempt': 1,
                    'status': 'failed', 'source': run_reference, 'artifactIds': []},), 'cursor-1')
        adapter = SyntheticAdapter()
        self.assertFalse(adapter.discover().capabilities['execution'])
        p = self.propose()
        self.approve(p)
        observed = self.observe_run(p)
        batch = adapter.collect(observed['engineRunId'], None)
        result = self.service.reconcile(observed['id'], list(batch.events), revision=self.revision())
        self.assertEqual(result['events']['synthetic-task-1']['status'], 'failed')
        self.assertEqual(len(self.store.flow()['actions']), 0)

    def test_invalid_evidence_batch_rolls_back_all_observations(self):
        p = self.propose()
        self.approve(p)
        observed = self.observe_run(p)
        valid = {'id': 'one', 'stage': 'filtered', 'attempt': 1, 'status': 'running',
            'source': 'synthetic trace', 'artifactIds': []}
        invalid = {**valid, 'id': 'two', 'artifactIds': ['missing']}
        before = self.store.flow()
        with self.assertRaises(RecordError):
            self.service.reconcile(observed['id'], [valid, invalid], revision=self.revision())
        self.assertEqual(self.store.flow(), before)

    def test_cli_roundtrip_no_execution(self):
        spec = self.root / 'proposal.json'
        spec.write_text(json.dumps(self.spec))
        def cli(*args):
            result = subprocess.run([sys.executable, '-B', '-m', 'saigen', '--project', str(self.root),
                'workflow', *args], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)
        p = cli('propose', '--spec', str(spec), '--revision', str(self.revision()))
        self.assertEqual(cli('show', p['id']), p)
        cli('approve', p['id'], '--digest', p['executionDigest'], '--revision', str(self.revision()))
        self.assertFalse(cli('engines')['executionSupported'])
        self.assertEqual(self.store.flow()['workflows']['runs'], {})
