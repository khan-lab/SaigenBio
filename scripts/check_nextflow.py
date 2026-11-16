#!/usr/bin/env python3
"""Explicit real-engine check; dataset and destination must be external to the checkout."""
import argparse
import collections
import copy
import csv
import json
from pathlib import Path
import shutil
import sys

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from saigen.store import Store, RecordError
from saigen.workflows.service import WorkflowService
from saigen.workflows.execution import execute
from saigen.workflows.adapters.nextflow import NextflowAdapter


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--destination', required=True)
    parser.add_argument('--dataset', required=True)
    args = parser.parse_args()
    destination = Path(args.destination).expanduser().resolve()
    if destination.is_relative_to(REPO) or destination.exists():
        parser.error('Choose a new external destination')
    destination.mkdir(parents=True)
    pipeline = destination / 'pipeline'
    shutil.copytree(REPO / 'examples/workflows/datacarpentry-variants', pipeline)
    store = Store(destination / 'project')
    store.init('Data Carpentry Nextflow integration check')
    state = store.snapshot('Data Carpentry E. coli variants', [Path(args.dataset).resolve()], ident='variants',
        note='Processed teaching dataset: https://raw.githubusercontent.com/datacarpentry/genomics-r-intro/main/episodes/data/combined_tidy_vcf.csv')
    service = WorkflowService(store)
    inspection = NextflowAdapter().inspect(str(pipeline), {})
    if not inspection['engine']['available']:
        raise RuntimeError('Nextflow and compatible Java are required')
    inspection['pipeline']['name'] = 'Data Carpentry variant summary'
    spec = {'schemaVersion': 1, 'engine': {'name': 'nextflow', 'version': inspection['engine']['version']},
        'pipeline': inspection['pipeline'], 'configuration': {'parameters': {'minimum_quality': 100}},
        'inputBindings': [{'name': 'samples', 'stateId': state['id'], 'artifactId': state['artifactIds'][0]}],
        'stages': [{'key': 'filtered', 'title': 'Quality-filtered variants', 'dependsOn': [],
            'expectedSummary': 'Variants with QUAL >= 100', 'expectedFiles': ['filtered.csv'], 'mapping': {'process': 'FILTER'}, 'method': {'tool': 'Python', 'summary': 'QUAL ≥ 100'}},
            {'key': 'summary', 'title': 'Variants per sample', 'dependsOn': ['filtered'],
             'expectedSummary': 'Variant counts per sample', 'expectedFiles': ['summary.tsv'], 'mapping': {'process': 'SUMMARY'}, 'method': {'tool': 'Python', 'summary': 'Count by sample_id'}}]}
    revision = lambda: store.flow()['revision']
    proposal = service.propose(spec, revision=revision())
    assert all(n['status'] == 'planned' for n in store.flow()['states'][1:])
    assert store.flow()['actions'] == []
    try:
        execute(service, proposal['id'], revision())
        raise AssertionError('Unapproved execution was accepted')
    except RecordError:
        pass
    assert store.flow()['workflows']['runs'] == {}
    def approve_and_run(p):
        service.approve(p['id'], p['executionDigest'], revision=revision())
        print('Executing approved test proposal: ' + p['id'], flush=True)
        return execute(service, p['id'], revision())
    result = approve_and_run(proposal)
    (destination / 'first-run.json').write_text(json.dumps(result, indent=2))
    assert result['status'] == 'completed', result
    assert result['engine']['source'] == 'version-verified-before-launch'
    assert result['stageMethods']['filtered']['tool'] == 'Python'
    assert result['stageMethods']['summary']['tool'] == 'Python'
    flow = store.flow()
    summary_id = result['stageNodes']['summary']
    node = next(n for n in flow['states'] if n['id'] == summary_id)
    output = store.artifact_path(flow['artifacts'][node['artifactIds'][0]])
    with Path(args.dataset).open() as stream:
        expected = collections.Counter(r['sample_id'] for r in csv.DictReader(stream) if float(r['QUAL']) >= 100)
    with output.open() as stream:
        actual = {r['sample']: int(r['variants']) for r in csv.DictReader(stream, delimiter='\t')}
    assert actual == dict(expected), (actual, expected)
    failed = copy.deepcopy(spec)
    failed['configuration']['parameters']['fail_summary'] = True
    failure_proposal = service.propose(failed, revision=revision())
    try:
        service.approve(failure_proposal['id'], proposal['executionDigest'], revision=revision())
        raise AssertionError('Old digest approved changed parameters')
    except RecordError:
        pass
    failure = approve_and_run(failure_proposal)
    assert failure['status'] == 'failed'
    assert failure['stages']['filtered']['status'] == 'completed'
    assert failure['stages']['summary']['status'] == 'failed'
    # A successful engine run with a missing promised output must still fail reconciliation.
    missing = copy.deepcopy(spec)
    missing['stages'][1]['expectedFiles'] = ['missing.tsv']
    missing_result = approve_and_run(service.propose(missing, revision=revision()))
    assert missing_result['exitCode'] == 0 and missing_result['status'] == 'failed'
    retry = execute(service, proposal['id'], revision())
    assert retry['status'] == 'completed'
    assert retry['stageNodes']['summary'] != summary_id
    old = next(n for n in store.flow()['states'] if n['id'] == summary_id)
    assert old['artifactIds'] == node['artifactIds']
    # Verify source drift blocks launch without adding an engine attempt.
    (pipeline / 'change.txt').write_text('source changed')
    before = len(store.flow()['workflows']['runs'])
    try:
        execute(service, proposal['id'], revision())
        raise AssertionError('Source drift was accepted')
    except RecordError:
        pass
    assert len(store.flow()['workflows']['runs']) == before
    report = {'engine': inspection['engine'], 'project': str(store.root), 'proposal': proposal['id'],
        'runs': [result['id'], failure['id'], missing_result['id'], retry['id']],
        'sourceDataset': str(Path(args.dataset).resolve()), 'expectedCounts': dict(expected),
        'checks': ['plan before execution', 'approval required', 'real outputs match independent counts',
            'failed task recorded', 'changed parameters need approval', 'missing output fails despite engine exit zero',
            'retry preserves original states', 'source drift blocks launch'], 'status': 'passed'}
    (destination / 'nextflow-check.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
