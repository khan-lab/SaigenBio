"""Local engine lifecycle; adapters never write recorder state."""
import copy
import hashlib
import os
from pathlib import Path
import shutil
import signal
import subprocess
from ..store import RecordError, now, uid, entity
from . import repository as repo
from .adapters.registry import adapter
from .models import execution_digest


def execute(service, proposal_id, revision):
    store = service.store
    proposal = service.show(proposal_id)
    engine = adapter(proposal['spec']['engine']['name'])
    launch = engine.prepare(proposal)
    # Verify artifacts before any process runs; stage immutable copies in this attempt.
    inputs = [(b, store.artifact(b['artifactId'])) for b in proposal['spec']['inputBindings']]
    for binding, artifact in inputs:
        store.artifact_path(artifact)
    run_id = uid('wrun')
    folder = store.home / 'workflows' / run_id
    folder.mkdir(parents=True)
    params = copy.deepcopy(proposal['spec']['configuration'].get('parameters', {}))
    (folder / 'inputs').mkdir()
    for binding, artifact in inputs:
        path = folder / 'inputs' / binding['name']
        shutil.copyfile(store.artifact_path(artifact), path)
        if hashlib.sha256(path.read_bytes()).hexdigest() != artifact['sha256']:
            raise RecordError('Input changed during staging')
        params[binding['name']] = str(path)
    staged = engine.stage(proposal, folder, params, launch)
    argv = list(staged.argv)
    config = folder / 'saigen.config'
    snapshots = [store.capture(p, role='code') for p in (folder / 'pipeline').rglob('*') if p.is_file()]
    snapshots += [store.capture(folder / 'params.json', role='environment'), store.capture(config, role='environment')]
    def reserve(flow):
        current = repo.proposal(flow, proposal_id)
        digest = execution_digest(current['spec'])
        if digest != proposal['executionDigest'] or not current['approval'] or current['approval']['executionDigest'] != digest:
            raise RecordError('A matching approval is required before execution')
        if any(r.get('status') == 'running' and r['proposalId'] == proposal_id for r in repo.collection(flow)['runs'].values()):
            raise RecordError('This proposal already has an active run')
        nodes = dict(current['stageNodes'])
        if any(r['proposalId'] == proposal_id for r in repo.collection(flow)['runs'].values()):
            # Preserve previous results; retries get their own result states.
            for key, old in list(nodes.items()):
                node = copy.deepcopy(entity(flow, 'states', old))
                node.update(id=uid('st'), status='planned', artifactIds=[], files=[], manifest=[], y=node['y']+210)
                for field in ('workflowEvidence', 'finishedAt', 'plan'):
                    node.pop(field, None)
                flow['states'].append(node)
                nodes[key] = node['id']
        for stage in current['spec']['stages']:
            node = entity(flow, 'states', nodes[stage['key']])
            node['planParents'] = [nodes[k] for k in stage['dependsOn']] or list(dict.fromkeys(b['stateId'] for b in current['spec']['inputBindings']))
            node['workflowRun'] = run_id
        record = {'id': run_id, 'proposalId': proposal_id, 'executionDigest': digest, 'engineRunId': None,
            'status': 'running', 'registeredAt': now(), 'events': {}, 'stages': {}, 'stageNodes': nodes,
            'argv': argv, 'cwd': str(folder), 'runnerPid': os.getpid(), 'sourceArtifacts': [a['id'] for a in snapshots]}
        repo.collection(flow)['runs'][run_id] = record
        flow['artifacts'].update({a['id']: a for a in snapshots})
        return {'run': copy.deepcopy(record)}, None
    store.update('workflow.launch_reserved', 'Recorder', reserve, revision)
    proc = None
    cancelled = False
    error = None
    exit_code = None
    old_handler = None
    import threading
    if threading.current_thread() is threading.main_thread():
        old_handler = signal.getsignal(signal.SIGTERM)
        def interrupted(signum, frame):
            raise KeyboardInterrupt
        signal.signal(signal.SIGTERM, interrupted)
    try:
        with (folder / 'stdout.log').open('wb') as out, (folder / 'stderr.log').open('wb') as err:
            proc = subprocess.Popen(argv, cwd=folder, stdout=out, stderr=err, start_new_session=True)
            exit_code = proc.wait()
    except KeyboardInterrupt:
        cancelled = True
        if proc:
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
    except OSError as exc:
        error = str(exc)
    finally:
        if old_handler is not None:
            signal.signal(signal.SIGTERM, old_handler)
    try:
        observations = list(engine.collect(str(folder), None).events)
        return finish(store, run_id, observations, exit_code, cancelled, error)
    except Exception as exc:
        def uncertain(flow):
            record = repo.run(flow, run_id)
            record.update(status='unknown', error=str(exc), exitCode=exit_code)
            return {'runId': run_id, 'error': str(exc)}, None
        store.update('workflow.reconciliation_failed', 'Recorder', uncertain)
        raise


def finish(store, run_id, observations, exit_code, cancelled=False, error=None):
    run = repo.run(store.flow(), run_id)
    proposal = repo.proposal(store.flow(), run['proposalId'])
    folder = Path(run['cwd'])
    captured = [store.capture(folder / name, role='log') for name in ('stdout.log', 'stderr.log', 'trace.tsv', '.nextflow.log', '.nextflow/history') if (folder / name).is_file()]
    history = folder / '.nextflow/history'
    engine_identity = None
    if history.is_file():
        columns = history.read_text().strip().split('\n')[-1].split('\t')
        if len(columns) >= 6:
            engine_identity = columns[5]
    results = {}
    for stage in proposal['spec']['stages']:
        rows = [r for r in observations if r['process'] == stage['mapping']['process']]
        result = {'status': 'unknown', 'rows': rows, 'outputs': [], 'error': None, 'scripts': []}
        for row in rows:
            work = Path(row.get('workdir', '')).resolve()
            script = work / '.command.sh'
            if work.is_relative_to((folder / 'work').resolve()) and script.is_file() and script.resolve().is_relative_to(work):
                result['scripts'].append(store.capture(script, role='code'))
        # This release deliberately requires exactly one observed task, no guessed aggregation.
        if len(rows) == 1:
            row = rows[0]
            status = row['status']
            result['status'] = {'FAILED': 'failed', 'ABORTED': 'cancelled'}.get(status, 'unknown')
            if status == 'COMPLETED' and row.get('exit') == '0':
                work = Path(row.get('workdir', '')).resolve()
                base = (folder / 'work').resolve()
                if not work.is_relative_to(base) or not work.is_dir():
                    result['error'] = 'Trace work directory is outside this attempt'
                else:
                    try:
                        for name in stage['expectedFiles']:
                            output = (work / name).resolve()
                            if not output.is_relative_to(work) or not output.is_file():
                                raise RecordError(f'Missing or external expected output: {name}')
                            result['outputs'].append(store.capture(output, name=name))
                        if not stage['expectedFiles']:
                            raise RecordError('A completed stage needs declared output evidence')
                        result['status'] = 'completed'
                    except (OSError, RecordError) as exc:
                        result.update(status='failed', error=str(exc), outputs=[])
        if cancelled and result['status'] == 'unknown':
            result['status'] = 'cancelled'
        results[stage['key']] = result
    def update(flow):
        record = repo.run(flow, run_id)
        if record['status'] != 'running':
            raise RecordError('Workflow attempt already finalized')
        record.update(status='cancelled' if cancelled else 'completed' if exit_code == 0 and all(r['status'] == 'completed' for r in results.values()) else 'failed',
            exitCode=exit_code, engineRunId=engine_identity, finishedAt=now(), error=error, observations=observations, logs=[a['id'] for a in captured])
        flow['artifacts'].update({a['id']: a for a in captured})
        for stage in proposal['spec']['stages']:
            key = stage['key']
            result = results[key]
            node = entity(flow, 'states', record['stageNodes'][key])
            node['plan'] = {k: copy.deepcopy(node[k]) for k in ('title','expectedSummary','expectedFiles','planParents')}
            node.update(status=result['status'], origin='workflow-recorded', performedBy='Nextflow', finishedAt=now(),
                workflowEvidence={'source': 'Nextflow trace; stage dependencies use the approved mapping', 'rows': result['rows'], 'error': result['error']},
                artifactIds=[a['id'] for a in result['outputs']], files=[a['name'] for a in result['outputs']])
            node['manifest'] = list(dict.fromkeys([b['artifactId'] for b in proposal['spec']['inputBindings']] + node['artifactIds']))
            flow['artifacts'].update({a['id']: a for a in result['outputs'] + result['scripts']})
            record['stages'][key] = {'stateId': node['id'], 'status': result['status'], 'error': result['error']}
            if result['rows']:
                flow['actions'].append({'id': uid('wa'), 'from': node['planParents'], 'to': node['id'],
                    'label': stage['mapping']['process'], 'command': '\n'.join(store.artifact_path(a).read_text() for a in result['scripts']) or 'Task script unavailable; inspect workflow trace', 'status': result['status'],
                    'origin': 'recorded', 'writtenBy': 'Recorder', 'performedBy': 'Nextflow', 'reason': 'Approved workflow stage mapping',
                    'methodSource': 'Nextflow trace; dependency edges are proposed stage mapping, not observed file-level lineage.',
                    'workflowRun': run_id, 'code': {'scriptArtifacts': [a['id'] for a in result['scripts']]}, 'inputArtifacts': [b['artifactId'] for b in proposal['spec']['inputBindings']],
                    'startedAt': record['registeredAt'], 'finishedAt': now(), 'exitCode': int(result['rows'][0]['exit']) if result['rows'][0].get('exit', '').lstrip('-').isdigit() else None, 'logs': record['logs']})
        return {'run': copy.deepcopy(record)}, None
    return repo.run(store.update('workflow.finished', 'Recorder', update), run_id)


def recover(store):
    """Lost supervisor contact means unknown; never infer success from files."""
    stale = []
    for record in repo.collection(store.flow())['runs'].values():
        if record.get('status') != 'running':
            continue
        try:
            os.kill(record['runnerPid'], 0)
        except ProcessLookupError:
            stale.append(record['id'])
        except PermissionError:
            pass
    if not stale:
        return {'recovered': []}
    def change(flow):
        for ident in stale:
            record = repo.run(flow, ident)
            if record.get('status') == 'running':
                record.update(status='unknown', error='Workflow supervisor was lost; completion is unknown.')
        return {'recovered': stale}, None
    store.update('workflow.contact_lost', 'Recorder', change)
    return {'recovered': stale}
