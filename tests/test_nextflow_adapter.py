"""Local adapter tests without installing or executing Nextflow."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from saigen.store import RecordError, Store
from saigen.workflows.adapters.nextflow import NextflowAdapter, source_digest
from saigen.workflows.adapters.base import EngineInfo
from saigen.workflows.execution import execute
from saigen.workflows.service import WorkflowService


class NextflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.pipeline = self.root / 'pipeline'
        self.pipeline.mkdir()
        (self.pipeline / 'main.nf').write_text('workflow {}')
        self.adapter = NextflowAdapter()
        self.adapter.executable = '/test/nextflow'
        self.info = EngineInfo('nextflow', '25.10.4', True, {})
        self.spec = {'engine': {'name': 'nextflow', 'version': '25.10.4'},
            'pipeline': {'source': str(self.pipeline), 'revision': 'local-content', 'contentDigest': source_digest(self.pipeline)},
            'configuration': {'parameters': {}}, 'inputBindings': [],
            'stages': [{'mapping': {'process': 'FILTER'}, 'expectedFiles': ['filtered.tsv']}]}

    def test_hash_covers_helper_code_and_symlinks_are_rejected(self):
        before = source_digest(self.pipeline)
        (self.pipeline / 'helper.py').write_text('print(1)')
        self.assertNotEqual(before, source_digest(self.pipeline))
        (self.pipeline / 'link').symlink_to(self.pipeline / 'main.nf')
        with self.assertRaises(RecordError):
            source_digest(self.pipeline)

    def test_version_source_and_mapping_validation(self):
        with patch.object(self.adapter, 'discover', return_value=self.info):
            self.assertIn('-with-trace', self.adapter.prepare({'spec': self.spec}).argv)
            for mutate in (lambda s: s['engine'].update(version='different'),
                           lambda s: s['pipeline'].update(contentDigest='changed'),
                           lambda s: s['stages'][0].update(expectedFiles=['../escape']),
                           lambda s: s['configuration'].update(profile='remote'),
                           lambda s: s['stages'][0].update(mapping={'process': []})):
                spec = copy.deepcopy(self.spec)
                mutate(spec)
                with self.assertRaises(RecordError):
                    self.adapter.prepare({'spec': spec})

    def test_static_inspection_does_not_evaluate_pipeline(self):
        with patch.object(self.adapter, 'discover', return_value=self.info), patch('subprocess.Popen') as proc:
            inspection = self.adapter.inspect(str(self.pipeline), {})
            self.assertEqual(inspection['pipeline']['contentDigest'], source_digest(self.pipeline))
            proc.assert_not_called()

    def test_trace_preserves_task_attempts_and_cached_status(self):
        (self.root / 'trace.tsv').write_text('task_id\tprocess\tstatus\texit\tattempt\tworkdir\n1\tFILTER\tFAILED\t1\t1\t/tmp/a\n2\tFILTER\tCACHED\t0\t2\t/tmp/b\n')
        rows = self.adapter.collect(str(self.root), None).events
        self.assertEqual([r['status'] for r in rows], ['FAILED', 'CACHED'])
        self.assertEqual([r['attempt'] for r in rows], ['1', '2'])

    def test_approval_failure_never_launches_engine(self):
        store = Store(self.root / 'project')
        store.init()
        data = self.root / 'data.tsv'
        data.write_text('x\n1\n')
        state = store.snapshot('Input', [data])
        spec = copy.deepcopy(self.spec)
        spec.update(schemaVersion=1, inputBindings=[{'name': 'input', 'stateId': state['id'], 'artifactId': state['artifactIds'][0]}])
        spec['stages'][0].update(key='filter', title='Filtered', dependsOn=[], expectedSummary='Filtered table')
        service = WorkflowService(store)
        p = service.propose(spec, revision=store.flow()['revision'])
        with patch('saigen.workflows.execution.adapter', return_value=self.adapter), patch.object(self.adapter, 'discover', return_value=self.info), patch('saigen.workflows.execution.subprocess.Popen') as proc:
            with self.assertRaises(RecordError):
                execute(service, p['id'], store.flow()['revision'])
            proc.assert_not_called()

        service.approve(p['id'], p['executionDigest'], revision=store.flow()['revision'])
        with patch('saigen.workflows.execution.adapter', return_value=self.adapter), patch.object(self.adapter, 'discover', return_value=self.info), patch('saigen.workflows.execution.subprocess.Popen') as proc, patch('saigen.workflows.execution.os.killpg') as kill:
            proc.return_value.pid = 1234
            proc.return_value.wait.side_effect = [KeyboardInterrupt, None]
            result = execute(service, p['id'], store.flow()['revision'])
            self.assertEqual(result['status'], 'cancelled')
            self.assertTrue(all(s['status'] == 'cancelled' for s in result['stages'].values()))
            kill.assert_called_once()
        def abandoned(flow):
            flow['workflows']['runs'][result['id']]['status'] = 'running'
            return {}, None
        store.update('test.abandoned', 'Recorder', abandoned)
        from saigen.workflows.execution import recover
        with patch('saigen.workflows.execution.os.kill', side_effect=ProcessLookupError):
            self.assertEqual(recover(store)['recovered'], [result['id']])
        self.assertEqual(store.flow()['workflows']['runs'][result['id']]['status'], 'unknown')
