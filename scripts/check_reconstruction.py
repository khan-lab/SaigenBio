"""Exercise mixed-source reconstruction with an isolated installed SaigenBio runtime."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import zipfile

SOURCE=Path(__file__).resolve().parent.parent


def worker(root, with_quarto):
    import saigen
    from saigen.store import Store
    from saigen.reports import Reports
    if Path(saigen.__file__).resolve().is_relative_to(SOURCE):
        raise RuntimeError('Use an installed runtime outside the source checkout')
    evidence=root/'evidence';evidence.mkdir()
    workspace=root/'workspace';workspace.mkdir()
    files={
        'input.csv':'sample,depth,value\nA,3,1.0\nB,7,2.0\nC,11,3.0\n',
        'filtered.csv':'sample,depth,value\nC,11,3.0\n',
        'chat.md':'Researcher: Explore a depth threshold on this synthetic teaching table.\nAssistant: I ran filter.py with --min-dp 5.\nResearcher: Preserve the source and do not draw biological conclusions.\n',
        'execution.log':'Reported command: python filter.py --input input.csv --output filtered.csv --min-dp 10\nReported exit: 0. No source hash or environment snapshot was saved.\n',
        'methods.md':'The script was edited after the conversation. Its historical version is unavailable. These values are synthetic.\n',
        'filter.py':'import argparse,csv\np=argparse.ArgumentParser()\np.add_argument("--input",required=True)\np.add_argument("--output",required=True)\np.add_argument("--min-dp",type=float,default=5)\na=p.parse_args()\nwith open(a.input,newline="") as f:\n r=csv.DictReader(f);cols=r.fieldnames;rows=[row for row in r if float(row["depth"])>=a.min_dp]\nwith open(a.output,"w",newline="") as f:\n w=csv.DictWriter(f,fieldnames=cols);w.writeheader();w.writerows(rows)\n'}
    for name,body in files.items():(evidence/name).write_text(body)
    original={name:hashlib.sha256((evidence/name).read_bytes()).hexdigest() for name in files}
    (root/'original-manifest.json').write_text(json.dumps(original,indent=2))
    store=Store(workspace)
    def cli(*args):
        result=subprocess.run([sys.executable,'-B','-I','-m','saigen','--project',str(workspace),'--actor','Synthetic acceptance',*map(str,args)],
                              cwd=workspace,text=True,capture_output=True,timeout=120)
        with (root/'commands.log').open('a') as log:log.write(' '.join(map(str,args))+'\n'+result.stdout+result.stderr+'\n')
        if result.returncode:raise RuntimeError('CLI check failed: '+result.stderr)
        return json.loads(result.stdout)
    def document(name,value):
        path=root/name;path.write_text(json.dumps(value,indent=2));return path
    def rev():return store.flow()['revision']
    cli('init','--existing-project',evidence,'--history-file',evidence/'chat.md','--agent','codex','--non-interactive','--no-start-viewer')
    def e(source,kind,note,location='line 1'):return {'source':source,'location':location,'kind':kind,'note':note}
    spec={'id':'mixed_history','sources':{name:str(evidence/name) for name in files},
          'states':[{'id':'input','title':'Preserved synthetic source table','files':[str(evidence/'input.csv')],
                     'evidence':[e('input.csv','direct','Table observed at import','lines 1–4')]},
                    {'id':'historical','title':'Preserved historical result','files':[str(evidence/'filtered.csv')],
                     'note':'Threshold conflicts between chat and log; original code version unresolved.',
                     'evidence':[e('filtered.csv','direct','The saved result exists','lines 1–2'),e('chat.md','reported','Chat claims threshold 5','line 2'),e('execution.log','reported','Log claims threshold 10')]}],
          'connections':[{'from':['input'],'to':'historical','label':'Reported filter; threshold unresolved',
                          'command':'Chat reports --min-dp 5; log reports --min-dp 10',
                          'evidence':[e('chat.md','reported','Command claim conflicts with the log','line 2'),e('execution.log','reported','Command claim differs from chat'),e('filter.py','inferred','Current code can filter; historical identity unknown','lines 1–12')]}]}
    cli('reconstruct','propose','--file',document('reconstruction.json',spec),'--revision',rev())
    if any(event['kind'].startswith('run.') for event in store.events()):raise RuntimeError('Reconstruction ran a command')
    for state in ('input','historical'):cli('reconstruct','accept','--id','mixed_history','--state',state,'--revision',rev())
    cli('reconstruct','reject','--id','mixed_history','--connection','mixed_history_0','--reason','Conflicting reported thresholds; historical code unavailable','--revision',rev())
    extension={'id':'later_evidence','relation':{'proposal':'mixed_history','kind':'extension','reason':'Add methodological caveat'},
               'sources':{'methods':str(evidence/'methods.md')},'existingStates':['historical'],'states':[],'connections':[],
               'addEvidence':[{'targetType':'state','targetId':'historical','evidence':[e('methods','reported','Historical script version is unavailable')]}]}
    cli('reconstruct','propose','--file',document('extension.json',extension),'--revision',rev())
    cli('reconstruct','accept','--id','later_evidence','--evidence','later_evidence_e0','--revision',rev())
    sources=store.flow()['reconstructions']['mixed_history']['sources']
    explanation={'kind':'limitation','states':['historical'],'summary':'A rerun cannot establish the unavailable historical code version.',
                 'evidenceKind':'reported','evidence':[{'type':'artifact','id':sources['methods.md'],'location':'line 1'}]}
    cli('explain','--file',document('limitation.json',explanation),'--revision',rev())
    flow=store.flow();input_node=next(n for n in flow['states'] if n['id']=='input');old=next(n for n in flow['states'] if n['id']=='historical')
    base={'originalStateId':'historical','inputStateIds':['input'],'inputArtifactIds':input_node['artifactIds'],
          'codeArtifactIds':[sources['filter.py']],'command':[sys.executable,'{code:0}','--input','{input:0}','--output','rerun.csv','--min-dp','10'],
          'outputs':['rerun.csv'],'criteria':[{'originalArtifactId':old['artifactIds'][0],'output':'rerun.csv','method':'sha256'},
                                           {'originalArtifactId':old['artifactIds'][0],'output':'rerun.csv','method':'numeric-table','keyColumns':['sample'],'columns':['depth','value'],'atol':0,'rtol':0}],
          'reason':'Test the logged threshold under the preserved current code, without claiming historical identity',
          'prerequisites':'Installed Python standard library; no downloads','resources':'Tiny local synthetic files; no paid compute'}
    outcomes=[]
    for label,change,expected in [('logged',{},'partial'),('chat',{'command':base['command'][:-1]+['5']},'different'),
                                  ('failed',{'command':[sys.executable,'-c','raise SystemExit(2)'],'codeArtifactIds':[]},'failed')]:
        proposal=cli('verify','propose','--file',document(label+'-verification.json',{**base,**change}),'--revision',rev())
        p=list(proposal['verifications']['proposals'].values())[-1]
        cli('verify','approve','--id',p['id'],'--digest',p['digest'],'--revision',rev())
        flow=cli('verify','execute','--id',p['id'],'--revision',rev())
        attempt=list(flow['verifications']['attempts'].values())[-1]
        if attempt['comparisonStatus']!=expected:raise RuntimeError('Unexpected comparison outcome: '+str(attempt))
        before=rev();cli('verify','compare','--id',attempt['id'],'--revision',before)
        if rev()!=before:raise RuntimeError('Repeated comparison duplicated history')
        outcomes.append({'case':label,'status':attempt['comparisonStatus'],'stateId':attempt['stateId'],'comparisonStateId':attempt['comparisonStateId']})
    flow=store.flow()
    if next(n for n in flow['states'] if n['id']=='historical')!=old:raise RuntimeError('Verification changed the original result record')
    actual={name:hashlib.sha256((evidence/name).read_bytes()).hexdigest() for name in files}
    if actual!=original:raise RuntimeError('Original evidence was modified')
    reports=Reports(store);selection=['historical',outcomes[0]['stateId'],outcomes[0]['comparisonStateId']]
    previews=[];before=rev()
    for template in ('results-summary','analysis-notebook','reproducibility-appendix'):
        preview=reports.preview(selection,before,template)
        folder=store.home/'reports'/preview['id'];snapshot=json.loads((folder/'snapshot.json').read_text())
        if not snapshot['explanations'] or not snapshot['verifications']['comparisons'] or not snapshot['evidenceFiles']:
            raise RuntimeError('Report omitted narrative or verification evidence')
        if not snapshot['reconstructionReviews'][0]['rejectedRelationships']:
            raise RuntimeError('Report omitted rejected relationship context')
        if with_quarto:
            reports.render_preview(preview['id'],before)
            deadline=time.monotonic()+180
            while time.monotonic()<deadline and reports.status(preview['id'])['status'] not in {'ready','failed'}:time.sleep(.1)
            if reports.status(preview['id'])['status']!='ready':raise RuntimeError('Quarto report failed: '+str(reports.status(preview['id'])))
            with zipfile.ZipFile(reports.file(preview['id'],'zip')) as bundle:
                if not any(name.startswith('evidence/') for name in bundle.namelist()):raise RuntimeError('Source bundle omitted preserved evidence')
        previews.append({'template':template,'folder':str(folder),'status':reports.status(preview['id'])['status']})
    if rev()!=before:raise RuntimeError('Report rendering changed analysis records')
    report={'status':'passed','runtime':sys.executable,'module':saigen.__file__,'originalsUnchanged':True,
            'mixedSourceConflictRetained':True,'selectiveReview':True,'laterEvidenceAppended':True,
            'verificationOutcomes':outcomes,'reports':previews,'workspace':str(workspace),
            'freshAgentCompliance':'Separate live-agent trial required; this check is deterministic.'}
    (root/'reconstruction-check.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination',type=Path,required=True)
    parser.add_argument('--python',type=Path,help='Python interpreter from an external installed-package check')
    parser.add_argument('--with-quarto',action='store_true')
    parser.add_argument('--worker',action='store_true',help=argparse.SUPPRESS)
    args=parser.parse_args();root=args.destination.expanduser().resolve()
    if root.is_relative_to(SOURCE) or SOURCE.is_relative_to(root):raise RuntimeError('Choose a new external trial directory')
    if args.worker:return worker(root,args.with_quarto)
    if not args.python:parser.error('--python is required')
    root.mkdir(parents=True,exist_ok=False)
    env=os.environ.copy()
    for key in ('SAIGEN_PROJECT','SAIGEN_SESSION','PYTHONPATH','PYTHONHOME'):env.pop(key,None)
    command=[str(args.python.expanduser().resolve()),'-B','-I',str(Path(__file__).resolve()),'--worker','--destination',str(root)]
    if args.with_quarto:command.append('--with-quarto')
    # Keep the venv executable path: resolving its symlink would lose site-packages.
    command[0]=str(args.python.expanduser().absolute())
    subprocess.run(command,env=env,check=True,timeout=600)


if __name__=='__main__':main()
