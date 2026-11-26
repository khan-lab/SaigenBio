"""Local Snakemake workflow tests with an opt-in real engine run."""

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from saigen.store import RecordError, Store
from saigen.workflows.adapters.snakemake import SnakemakeAdapter
from saigen.workflows.execution import execute
from saigen.workflows.service import WorkflowService


SNAKEFILE = """
rule make_copy:
    input: config["records"]
    output: "copied.txt"
    shell: "cat {input:q} > {output:q}"

rule summarize:
    input: "copied.txt"
    output: "lines.txt"
    params: fail=config.get("fail", "false")
    shell: "test {params.fail:q} = false && wc -l < {input:q} > {output:q}"
"""


class SnakemakeTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source = self.root / 'source'
        self.snakefile = self.source / 'workflow' / 'Snakefile'
        self.snakefile.parent.mkdir(parents=True)
        self.snakefile.write_text(SNAKEFILE)

    def test_static_inspection_fingerprints_source_and_ignores_runtime_files(self):
        adapter = SnakemakeAdapter()
        adapter.executable = None
        with patch('saigen.workflows.adapters.snakemake.subprocess.run') as run:
            original = adapter.inspect(str(self.source), {})
            self.assertEqual(original, adapter.inspect(str(self.snakefile), {}))
            self.assertEqual(original['files'], ['workflow/Snakefile'])
            (self.source / '.snakemake').mkdir()
            (self.source / '.snakemake' / 'log').write_text('engine cache')
            self.assertEqual(original, adapter.inspect(str(self.source), {}))
            self.snakefile.write_text('raise RuntimeError("must not run")')
            self.assertNotEqual(original['pipeline'], adapter.inspect(str(self.source), {})['pipeline'])
            run.assert_not_called()

    def test_collect_matches_job_ids_and_does_not_infer_completion(self):
        events = [
            {'event': 'JOB_INFO', 'jobid': 0, 'rule_name': 'copy', 'output': ['copied.txt']},
            {'event': 'JOB_FINISHED', 'job_id': 0},
            {'event': 'JOB_INFO', 'jobid': 1, 'rule_name': 'summary'},
            {'event': 'JOB_ERROR', 'jobid': 1},
            {'event': 'JOB_INFO', 'jobid': 2, 'rule_name': 'skipped'},
        ]
        (self.root / 'snakemake-events.jsonl').write_text(
            ''.join(json.dumps(event) + '\n' for event in events) + '{"truncated":')
        rows = SnakemakeAdapter().collect(str(self.root)).events
        self.assertEqual([row['status'] for row in rows], ['COMPLETED', 'FAILED', 'STARTED'])
        self.assertEqual(rows[0]['declaredOutputs'], ['copied.txt'])

    @unittest.skipUnless(os.environ.get('SAIGEN_TEST_SNAKEMAKE'), 'Set SAIGEN_TEST_SNAKEMAKE=1 for real engine execution')
    def test_real_engine_approval_success_and_failed_attempt(self):
        engine = SnakemakeAdapter()
        inspection = engine.inspect(str(self.source), {})
        self.assertTrue(inspection['engine']['capabilities']['localExecution'], inspection['engine'])
        store = Store(self.root / 'project')
        store.init()
        data = self.root / 'original.txt'
        data.write_text('first\nsecond\n')
        state = store.snapshot('Example records', [data])
        spec = {'schemaVersion': 1, 'engine': {'name': 'snakemake', 'version': inspection['engine']['version']},
            'pipeline': inspection['pipeline'],
            'inputBindings': [{'name': 'records', 'artifactId': state['artifactIds'][0], 'stateId': state['id']}],
            'configuration': {'targets': ['lines.txt'], 'cores': 1},
            'stages': [
                {'key': 'copy', 'title': 'Copied records', 'dependsOn': [], 'expectedSummary': 'Preserved records',
                 'expectedFiles': ['copied.txt'], 'mapping': {'rule': 'make_copy'}},
                {'key': 'summary', 'title': 'Line count', 'dependsOn': ['copy'], 'expectedSummary': 'Count the records',
                 'expectedFiles': ['lines.txt'], 'mapping': {'rule': 'summarize'}},
            ]}
        service = WorkflowService(store)
        revision = lambda: store.flow()['revision']
        for failure in ('none', 'job', 'output'):
            parameters = {'fail': 'true'} if failure == 'job' else {}
            spec['configuration']['parameters'] = parameters
            if failure == 'output':
                spec['stages'][1]['expectedFiles'] = ['copied.txt']
            proposal = service.propose(spec, revision=revision())
            planned = service.show(proposal['id'])
            self.assertIsNone(planned['approval'])
            self.assertTrue(all(n['status'] == 'planned' for n in store.flow()['states']
                if n['id'] in planned['stageNodes'].values()))
            with self.assertRaisesRegex(RecordError, 'approval'):
                execute(service, proposal['id'], revision())
            service.approve(proposal['id'], proposal['executionDigest'], revision=revision())
            run = execute(service, proposal['id'], revision())
            logs = ''.join(store.artifact_path(store.artifact(ident)).read_text() for ident in run['logs'])
            self.assertEqual(run['stages']['copy']['status'], 'completed', logs)
            self.assertEqual(run['status'], 'completed' if failure == 'none' else 'failed', logs)
            self.assertTrue(run['engineRunId'], logs)
            flow = store.flow()
            result = next(n for n in flow['states'] if n['id'] == run['stageNodes']['summary'])
            self.assertEqual(result['performedBy'], 'Snakemake')
            self.assertEqual(result['plan']['expectedFiles'], spec['stages'][1]['expectedFiles'])
            action = next(a for a in flow['actions'] if a['to'] == result['id'])
            self.assertEqual(action['from'], [run['stageNodes']['copy']])
            self.assertIn('wc -l', action['command'])
            if failure == 'none':
                self.assertEqual(store.artifact_path(store.artifact(result['artifactIds'][0])).read_text().strip(), '2')
            else:
                self.assertEqual(result['status'], 'failed', logs)
                self.assertEqual(result['artifactIds'], [])
                if failure == 'output':
                    self.assertEqual(run['exitCode'], 0)
                    self.assertIn('not declared by the observed job', result['workflowEvidence']['error'])
            self.assertEqual(data.read_text(), 'first\nsecond\n')
            self.assertFalse((self.source / 'copied.txt').exists())
