"""Reviewed verification attempts and explicit comparisons with preserved originals."""
import copy
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil

from .comparison import compare as compare_artifacts
from .records import RecordError, entity, now, text, uid
from .runner import run, local_output
from .store import digest


def collection(flow):
    return flow.setdefault('verifications',{'proposals':{},'attempts':{}})


def proposal(flow, ident):
    try:return collection(flow)['proposals'][ident]
    except KeyError as exc:raise RecordError('Unknown verification proposal') from exc


def content_digest(spec):
    return hashlib.sha256(json.dumps(spec,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def accepted(node):
    if node['status'] not in {'imported','completed','saved'} or node.get('reconstruction',{}).get('review','accepted')!='accepted':
        raise RecordError('Verification requires accepted recorded results and inputs')


def preserved(store, flow, ident):
    record=flow['artifacts'].get(ident) if isinstance(ident,str) else None
    if not record or record.get('storage')!='preserved':raise RecordError('Verification needs preserved registered artifacts')
    return store.artifact_path(record)


def propose(store, spec, revision, actor='AI agent'):
    required={'originalStateId','inputStateIds','inputArtifactIds','codeArtifactIds','command','outputs','criteria','reason','prerequisites','resources'}
    if not isinstance(spec,dict) or not required<=spec.keys() or spec.keys()-required-{'environmentArtifactIds','toolVersions'}:
        raise RecordError('Verification proposal needs original, inputs, code, command, outputs, criteria, reason, prerequisites and resources')
    spec=copy.deepcopy(spec)
    text(spec['originalStateId'],'original state',100,True)
    for key in ('inputStateIds','inputArtifactIds','codeArtifactIds','environmentArtifactIds','toolVersions','command','outputs'):
        values=spec.setdefault(key,[])
        if not isinstance(values,list) or len(values)>100 or any(not isinstance(v,str) or not v for v in values):
            raise RecordError('Invalid '+key)
    if not spec['inputStateIds'] or not spec['command'] or not spec['outputs']:
        raise RecordError('Supply input states, command and outputs')
    if len(set(spec['inputStateIds']))!=len(spec['inputStateIds']):raise RecordError('Input state IDs must be unique')
    if len(set(spec['outputs']))!=len(spec['outputs']):raise RecordError('Duplicate output name')
    for name in spec['outputs']:local_output(Path('/placeholder'),name)
    for key in ('reason','prerequisites','resources'):text(spec[key],key,10000,True)
    criteria=spec['criteria']
    if not isinstance(criteria,list) or not 1<=len(criteria)<=100:raise RecordError('Supply 1–100 artifact comparison criteria')
    for criterion in criteria:
        required_criterion={'originalArtifactId','output','method'}
        numeric={'keyColumns','columns','atol','rtol','delimiter'}
        if not isinstance(criterion,dict) or not required_criterion<=criterion.keys() or criterion.keys()-required_criterion-numeric:
            raise RecordError('Invalid comparison criterion')
        text(criterion['originalArtifactId'],'original artifact',100,True)
        if not isinstance(criterion['output'],str) or criterion['output'] not in spec['outputs']:raise RecordError('Comparison output was not declared')
        if criterion['method'] not in ('sha256','numeric-table'):raise RecordError('Supported comparators: sha256 and numeric-table')
        if criterion['method']=='sha256' and criterion.keys() & numeric:raise RecordError('SHA256 comparison does not use numeric options')
        if criterion['method']=='numeric-table':
            for key in ('keyColumns','columns'):
                values=criterion.get(key)
                if not isinstance(values,list) or not values or len(values)>50 or any(not isinstance(v,str) or not v for v in values) or len(set(values))!=len(values):raise RecordError('Numeric comparison requires unique keyColumns and columns')
            if set(criterion['keyColumns'])&set(criterion['columns']):raise RecordError('Numeric columns cannot also be key columns')
            for key in ('atol','rtol'):
                value=criterion.get(key)
                if type(value) not in (int,float) or not math.isfinite(value) or value<0:raise RecordError('Supply explicit finite nonnegative tolerances')
            if criterion.setdefault('delimiter',',') not in (',','\t'):raise RecordError('Use CSV or TSV delimiter')
    flow=store.flow();original=entity(flow,'states',spec['originalStateId']);accepted(original)
    available=set()
    for sid in spec['inputStateIds']:
        node=entity(flow,'states',sid);accepted(node)
        available.update(node.get('manifest',[])+node.get('artifactIds',[]))
    if any(aid not in available for aid in spec['inputArtifactIds']):raise RecordError('Input artifact must belong to a declared input state')
    artifacts=set(spec['inputArtifactIds']+spec['codeArtifactIds']+spec['environmentArtifactIds'])
    for criterion in criteria:
        if criterion['originalArtifactId'] not in original.get('artifactIds',[]):raise RecordError('Comparison artifact must belong to the original result')
        artifacts.add(criterion['originalArtifactId'])
    spec['artifactHashes']={aid:digest(preserved(store,flow,aid)) for aid in sorted(artifacts)}
    executable=shutil.which(spec['command'][0])
    spec['runtime']={'executable':str(Path(executable).resolve()) if executable else None,
                     'sha256':digest(executable) if executable else None}
    for argument in spec['command']:
        if Path(argument).suffix.lower() in {'.py','.r','.sh','.pl','.jl','.ipynb'} and '{code:' not in argument:
            raise RecordError('Use a preserved {code:N} placeholder for script arguments')
        for index in re.findall(r'\{input:(\d+)\}',argument):
            if int(index)>=len(spec['inputArtifactIds']):raise RecordError('Unresolved input placeholder')
        for index in re.findall(r'\{code:(\d+)\}',argument):
            if int(index)>=len(spec['codeArtifactIds']):raise RecordError('Unresolved code placeholder')
    ident=uid('verify');record={'id':ident,'spec':spec,'digest':content_digest(spec),'writtenBy':actor,'createdAt':now(),'approval':None,'cancelled':None}
    def change(flow):
        # Recheck lifecycle inside the revision-checked transaction.
        accepted(entity(flow,'states',spec['originalStateId']))
        for sid in spec['inputStateIds']:accepted(entity(flow,'states',sid))
        collection(flow)['proposals'][ident]=record
        return {'verification':record},None
    return store.update('verification.proposed',actor,change,revision)


def approve(store, ident, expected_digest, revision, actor='AI agent'):
    def change(flow):
        record=proposal(flow,ident)
        if record.get('cancelled'):raise RecordError('Verification proposal was cancelled')
        if expected_digest!=record['digest'] or expected_digest!=content_digest(record['spec']):raise RecordError('Approval must match the concrete verification digest')
        record['approval']={'digest':expected_digest,'declaredBy':actor,'at':now(),'authenticatedHuman':False}
        return {'verification':copy.deepcopy(record)},None
    return store.update('verification.approved',actor,change,revision)


def cancel(store, ident, reason, revision, actor='AI agent'):
    text(reason,'cancellation reason',10000,True)
    def change(flow):
        record=proposal(flow,ident)
        if any(a['proposalId']==ident and a['status']=='running' for a in collection(flow)['attempts'].values()):raise RecordError('Stop the active attempt before cancelling future verification runs')
        record['cancelled']={'by':actor,'at':now(),'reason':reason}
        return {'verification':copy.deepcopy(record)},None
    return store.update('verification.cancelled',actor,change,revision)


def execute(store, ident, revision, actor='AI agent'):
    flow=store.flow();record=proposal(flow,ident);spec=record['spec']
    if record.get('cancelled') or not record.get('approval') or record['approval']['digest']!=record['digest'] or content_digest(spec)!=record['digest']:
        raise RecordError('Review and approve this verification configuration before execution')
    for aid,expected in spec['artifactHashes'].items():
        if digest(preserved(store,flow,aid))!=expected:raise RecordError('A verification artifact changed')
    runtime=spec['runtime']
    if not runtime['executable'] or digest(runtime['executable'])!=runtime['sha256']:
        raise RecordError('Prepare the runtime and publish a new proposal before execution')
    command=[runtime['executable'],*spec['command'][1:]]
    code=[str(preserved(store,flow,aid)) for aid in spec['codeArtifactIds']]
    for index,argument in enumerate(command):
        for ci,path in enumerate(code):argument=argument.replace('{code:'+str(ci)+'}',path)
        if '{code:' in argument:raise RecordError('Unresolved code placeholder')
        command[index]=argument
    attempt_id=uid('va');state_id=uid('st')
    def reserve(flow):
        current=proposal(flow,ident)
        if current.get('cancelled') or not current.get('approval') or current['approval']['digest']!=current['digest']:raise RecordError('Verification approval is no longer active')
        if any(a['proposalId']==ident and a['status']=='running' for a in collection(flow)['attempts'].values()):raise RecordError('This proposal has an unfinished attempt; inspect or compare it before retrying')
        accepted(entity(flow,'states',spec['originalStateId']))
        collection(flow)['attempts'][attempt_id]={'id':attempt_id,'proposalId':ident,'stateId':state_id,'status':'running','startedAt':now(),'writtenBy':actor,'comparisonStateId':None,'supervisorPid':os.getpid()}
        return {'verificationAttempt':copy.deepcopy(collection(flow)['attempts'][attempt_id])},None
    store.update('verification.started',actor,reserve,revision)
    try:
        run(store,spec['inputStateIds'],'Verification attempt',command,inputs=['artifact:'+aid for aid in spec['inputArtifactIds']],
            outputs=spec['outputs'],actor=actor,reason=spec['reason'],ident=state_id,scripts=code,
            environment_files=[str(preserved(store,flow,aid)) for aid in spec['environmentArtifactIds']],tool_versions=spec['toolVersions'])
    except (RecordError,OSError) as exc:
        def failed(flow):
            attempt=collection(flow)['attempts'][attempt_id];attempt.update(status='failed',error=str(exc))
            return {'verificationAttempt':copy.deepcopy(attempt)},None
        store.update('verification.preparation_failed',actor,failed)
        raise
    return compare(store,attempt_id,store.flow()['revision'],actor)


def recover(store, attempt_id, revision, actor='AI agent'):
    def change(flow):
        attempt=collection(flow)['attempts'].get(attempt_id)
        if not attempt or attempt.get('comparisonStateId'):raise RecordError('No unfinished verification attempt')
        try:
            os.kill(attempt['supervisorPid'],0)
        except ProcessLookupError:
            pass
        except (KeyError,PermissionError) as exc:
            raise RecordError('Supervisor liveness could not be established') from exc
        else:
            raise RecordError('The verification supervisor is still running')
        attempt.update(status='unknown',error='Verification supervisor was lost; completion is unknown.')
        for action in flow['actions']:
            if action['to']==attempt['stateId'] and action['status']=='running':
                action.update(status='unknown',error=attempt['error'])
                entity(flow,'states',attempt['stateId'])['status']='unknown'
        return {'verificationAttempt':copy.deepcopy(attempt)},None
    return store.update('verification.contact_lost',actor,change,revision)


def compare(store, attempt_id, revision, actor='AI agent'):
    flow=store.flow()
    attempt=collection(flow)['attempts'].get(attempt_id)
    if not attempt:raise RecordError('Unknown verification attempt')
    if attempt.get('comparisonStateId'):return flow
    record=proposal(flow,attempt['proposalId']);spec=record['spec']
    candidate=next((n for n in flow['states'] if n['id']==attempt['stateId']),None)
    if not candidate:raise RecordError('No observed attempt exists; inspect the interrupted preparation before retrying')
    if candidate['status'] in {'running','planned'}:raise RecordError('Wait for the attempt or recover lost recorder contact before comparison')
    outputs={flow['artifacts'][aid]['name']:aid for aid in candidate.get('artifactIds',[])}
    results=[]
    for criterion in spec['criteria']:
        output_id=outputs.get(criterion['output'])
        result={'criterion':copy.deepcopy(criterion),'originalArtifactId':criterion['originalArtifactId'],'candidateArtifactId':output_id}
        try:
            if not output_id:raise RecordError('Declared comparison output is missing')
            result.update(compare_artifacts(preserved(store,flow,criterion['originalArtifactId']),preserved(store,flow,output_id),criterion))
        except (RecordError,OSError,ValueError,UnicodeError,csv.Error) as exc:
            result.update(status='unavailable',reason=str(exc))
        results.append(result)
    statuses={r['status'] for r in results}
    status='failed' if candidate['status']!='completed' else 'match' if statuses=={'match'} else 'different' if statuses=={'different'} else 'unavailable' if statuses=={'unavailable'} else 'partial'
    report={'proposalId':record['id'],'attemptId':attempt_id,'originalStateId':spec['originalStateId'],'candidateStateId':candidate['id'],
            'status':status,'criteria':results,'recordedAt':now(),'meaning':'Only the stated criteria and recorded conditions were tested. This does not prove historical execution or scientific correctness.'}
    folder=store.home/'verification-comparisons'/attempt_id;folder.mkdir(parents=True,exist_ok=True)
    path=folder/'comparison.json';path.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    artifact=store.capture(path,role='output');comparison_id=uid('st')
    def change(flow):
        current=collection(flow)['attempts'][attempt_id]
        if current.get('comparisonStateId'):raise RecordError('Attempt was already compared')
        node=entity(flow,'states',candidate['id'])
        flow['artifacts'][artifact['id']]=artifact
        flow['states'].append({'id':comparison_id,'title':'Verification comparison · '+status,'note':report['meaning'],
            'status':'completed','origin':'verification-comparison','writtenBy':actor,'performedBy':'SaigenBio',
            'createdAt':now(),'x':node['x']+320,'y':node['y'],'artifactIds':[artifact['id']],'manifest':[artifact['id']],
            'files':[artifact['name']],'references':[],'verificationComparison':report})
        flow['actions'].append({'id':uid('cmp'),'from':list(dict.fromkeys([spec['originalStateId'],candidate['id']])),'to':comparison_id,
            'label':'Compare preserved artifacts','command':'','reason':spec['reason'],'status':'completed',
            'origin':'verification-comparison','writtenBy':actor,'performedBy':'SaigenBio','createdAt':now(),
            'methodSource':'Observed artifact comparison by SaigenBio; criteria do not establish historical execution.'})
        current.update(status=candidate['status'],comparisonStatus=status,comparisonStateId=comparison_id,finishedAt=now())
        return {'state':copy.deepcopy(flow['states'][-1]),'verificationComparison':report,'verificationAttempt':copy.deepcopy(current)},None
    return store.update('verification.compared',actor,change,revision)
