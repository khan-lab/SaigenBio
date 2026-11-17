"""Attributed reconstructions of existing evidence; no execution or folder discovery."""
import copy
import hashlib
import json
from pathlib import Path
from .store import RecordError, now, text, ID


def setup_context(root, existing, sources):
    directory=Path(existing).expanduser()
    directory=(directory if directory.is_absolute() else root/directory).resolve(strict=True)
    if not directory.is_dir():raise RecordError('Existing project must be a directory')
    files=[]
    for value in sources:
        path=Path(value).expanduser()
        path=(path if path.is_absolute() else root/path).resolve(strict=True)
        if not path.is_file():raise RecordError('History source must be a file')
        files.append(str(path))
    return {'directory':str(directory),'sources':files,'intent':'reconstruct-existing-analysis'}


def propose(store, spec, revision, actor):
    if not isinstance(spec,dict) or set(spec)!={'id','sources','states','connections'}:raise RecordError('Proposal needs id, sources, states, connections')
    ident=spec['id']
    if not isinstance(ident,str) or not ID.fullmatch(ident):raise RecordError('Invalid reconstruction ID')
    if not isinstance(spec['states'],list) or not 1<=len(spec['states'])<=50:raise RecordError('Supply 1–50 states')
    if not isinstance(spec['sources'],dict) or not spec['sources']:raise RecordError('Supply named evidence sources')
    if len(spec['sources'])>50 or any(not isinstance(k,str) or not isinstance(v,str) for k,v in spec['sources'].items()):raise RecordError('Supply up to 50 named source paths')
    if not isinstance(spec['connections'],list) or len(spec['connections'])>100:raise RecordError('Supply up to 100 connections')
    for item in spec['states']:
        if not isinstance(item,dict) or not {'id','title','evidence'}<=item.keys() or item.keys()-{'id','title','note','files','evidence'}:raise RecordError('State needs id, title, evidence and optional note/files')
        if not isinstance(item.get('files',[]),list) or len(item.get('files',[]))>100 or any(not isinstance(v,str) for v in item.get('files',[])):raise RecordError('Supply up to 100 file paths per state')
    for item in spec['connections']:
        if not isinstance(item,dict) or not {'from','to','evidence'}<=item.keys() or item.keys()-{'from','to','evidence','label','command'}:raise RecordError('Invalid connection')
        if not isinstance(item['from'],list) or any(not isinstance(v,str) for v in item['from']) or not isinstance(item['to'],str):raise RecordError('Invalid connection endpoints')
    records={}
    for key,value in spec['sources'].items():
        path=Path(value).expanduser();path=path if path.is_absolute() else store.root/path
        records[key]=store.capture(path,role='input')
    fingerprint=hashlib.sha256(json.dumps({'spec':spec,'hashes':{k:v['sha256'] for k,v in records.items()}},sort_keys=True).encode()).hexdigest()
    def evidence(value):
        if not isinstance(value,list) or not value:raise RecordError('Each state and connection needs evidence')
        result=[]
        for entry in value:
            if not isinstance(entry,dict) or set(entry)!={'source','location','kind','note'} or not isinstance(entry['source'],str) or not isinstance(entry['kind'],str) or entry['source'] not in records or entry['kind'] not in {'direct','reported','inferred','unresolved'}:raise RecordError('Evidence needs source, location, kind and note')
            result.append({**entry,'artifactId':records[entry['source']]['id'],'location':text(entry['location'],'source location',1000,True),'note':text(entry['note'],'evidence note',4000,True)})
        return result
    nodes=[];ids=set()
    for index,item in enumerate(spec['states']):
        sid=item['id']
        if not isinstance(sid,str) or not ID.fullmatch(sid) or sid in ids:raise RecordError('Invalid or repeated state ID')
        ids.add(sid)
        files=[]
        for value in item.get('files',[]):
            path=Path(value).expanduser();files.append(store.capture(path if path.is_absolute() else store.root/path,role='output'))
        nodes.append({'id':sid,'title':text(item['title'],'title',120,True),'note':text(item.get('note',''),'note'),'x':index*300,'y':0,'status':'imported','origin':'reconstruction-draft','writtenBy':actor,'performedBy':None,'createdAt':now(),'artifactIds':[v['id'] for v in files],'manifest':[v['id'] for v in files],'files':[v['name'] for v in files],'references':[], 'reconstruction':{'id':ident,'evidence':evidence(item['evidence']),'review':'draft'}})
        records.update({v['id']:v for v in files})
    actions=[]
    for index,item in enumerate(spec['connections']):
        if not item['from'] or any(v not in ids for v in item['from']) or item['to'] not in ids:raise RecordError('Connections must refer to proposal states')
        actions.append({'id':ident+'_'+str(index),'from':item['from'],'to':item['to'],'label':text(item.get('label','Reconstructed relationship'),'label',160,True),'command':text(item.get('command',''),'reported command'),'status':'unknown','origin':'reconstructed','writtenBy':actor,'performedBy':None,'createdAt':now(),'reconstruction':{'id':ident,'evidence':evidence(item['evidence']),'review':'draft'},'methodSource':'Reconstructed relationship; execution was not observed by SaigenBio.'})
    def change(flow):
        proposals=flow.setdefault('reconstructions',{})
        if ident in proposals:
            raise RecordError('Reconstruction ID already exists; inspect it before importing again')
        if any(p['fingerprint']==fingerprint for p in proposals.values()):raise RecordError('This proposal was already imported')
        if ids.intersection({n['id'] for n in flow['states']} | {sid for p in proposals.values() for sid in p['states']}):raise RecordError('A state ID already exists')
        flow['artifacts'].update({v['id']:v for v in records.values()})
        for node in nodes:node['y']=len(flow['states'])*190
        flow['states'].extend(nodes);flow['actions'].extend(actions)
        proposals[ident]={'id':ident,'status':'draft','writtenBy':actor,'createdAt':now(),'fingerprint':fingerprint,'spec':copy.deepcopy(spec),'states':list(ids),'actions':[a['id'] for a in actions],'sources':{k:v['id'] for k,v in records.items() if k in spec['sources']}}
        return {'reconstruction':proposals[ident]},None
    return store.update('reconstruction.proposed',actor,change,revision)


def review(store, ident, decision, revision, actor):
    if decision not in {'accept','reject'}:raise RecordError('Choose accept or reject')
    def change(flow):
        proposal=flow.get('reconstructions',{}).get(ident)
        if not proposal or proposal['status']!='draft':raise RecordError('No pending reconstruction with this ID')
        if decision=='reject':
            ids=set(proposal['states']);aids=set(proposal['actions'])
            if any(ids.intersection(p['spec'].get('contextStateIds',[])) for p in flow.get('workflows',{}).get('proposals',{}).values()):raise RecordError('A workflow references this reconstruction')
            if any(a['id'] not in aids and (a['to'] in ids or ids.intersection(a['from'])) for a in flow['actions']) or any(n['id'] not in ids and ids.intersection(n.get('planParents',[])) for n in flow['states']):raise RecordError('Other work depends on this reconstruction')
            proposal['archivedStates']=[n for n in flow['states'] if n['id'] in ids]
            proposal['archivedActions']=[a for a in flow['actions'] if a['id'] in aids]
            flow['states']=[n for n in flow['states'] if n['id'] not in ids];flow['actions']=[a for a in flow['actions'] if a['id'] not in aids]
        else:
            for item in flow['states']+flow['actions']:
                if item.get('reconstruction',{}).get('id')==ident:
                    item['reconstruction'].update(review='accepted',reviewedBy=actor,reviewedAt=now())
                    if item in flow['states']:item['origin']='reconstructed'
        proposal.update(status='accepted' if decision=='accept' else 'rejected',reviewedBy=actor,reviewedAt=now())
        return {'reconstruction':proposal},None
    return store.update('reconstruction.reviewed',actor,change,revision)
