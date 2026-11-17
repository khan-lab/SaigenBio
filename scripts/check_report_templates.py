#!/usr/bin/env python3
"""Render all report templates using synthetic evidence outside the checkout."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from saigen.store import Store
from saigen.reports import Reports, sha
from saigen.report_templates import TEMPLATES


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination',required=True,type=Path,help='A new directory outside the source checkout')
    args=parser.parse_args()
    destination=args.destination.expanduser().resolve()
    if destination.is_relative_to(Path(__file__).resolve().parent.parent):
        parser.error('Use an external destination')
    destination.mkdir(parents=True,exist_ok=False)
    store=Store(destination/'workspace');store.init('Synthetic report layout check')
    root=store.root
    files=[]
    for i in (1,2):
        figure=root/f'figure-{i}.svg'
        figure.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="600" height="240"><rect width="600" height="240" fill="#f5f7f1"/><text x="25" y="40" font-size="20">Synthetic figure {i}</text><path d="M30 190 L140 120 L260 160 L400 70 L560 40" stroke="#294e43" stroke-width="4" fill="none"/></svg>')
        files.append(figure)
    table=root/'example.tsv'
    table.write_text('sample\tretained\tremoved\tcomment\n'+''.join(f'Sample-{i}\t{i*7}\t{i}\tIllustrative record\n' for i in range(12)))
    files.append(table)
    store.snapshot('Synthetic results',files,ident='results',note='Synthetic evidence for layout inspection; no biological analysis was performed.')
    store.snapshot('Second result',files,ident='second',note='A second result reuses preserved figures and source.')
    store.snapshot('Failed attempt',[],ident='failed',note='Synthetic failure fixture; outputs are unavailable.')
    store.plan('Planned result',['results'],'An expected comparison table.',ident='plan',details='Compare the recorded result tables.',outputs=['comparison.tsv'])
    script=root/'method.py'
    script.write_text('# Synthetic source; never executed by this check.\n'+''.join(f'# Explanation line {i}: a modest description of a method operation and its relevant parameter.\n' for i in range(90))+'print("display only")\n')
    code=store.capture(script,role='code')
    flow=store.flow();flow['artifacts'][code['id']]=code
    for node in flow['states']:
        if node['id'] in {'results','second'}:node['status']='completed'
        if node['id']=='failed':node['status']='failed'
    flow['actions']=[{'id':'fixture-'+target,'to':target,'from':[],'status':'failed' if target=='failed' else 'completed',
        'argv':['python','method.py','--minimum-depth','5','--description','A deliberately long parameter value '+('with readable wrapping '*12)],
        'reason':'Exercise report formatting without running an analysis.', 'writtenBy':'Synthetic fixture', 'performedBy':'Synthetic fixture',
        'exitCode':1 if target=='failed' else 0,'error':'Illustrative failure' if target=='failed' else '',
        'inputArtifacts':[], 'code':{'scriptArtifacts':[code['id']],'explanation':{'summary':'Illustrative method with a depth threshold of 5. '+('This explanation tests text wrapping. '*10),'recordedBy':'Synthetic fixture','excerpts':[{'artifactId':code['id'],'start':2,'end':4,'text':'\n'.join(script.read_text().splitlines()[1:4])}]}},
        'environment':{'declaredToolVersions':['Python (synthetic declaration)'], 'notes':'Environment replay is not established.'}}
        for target in ('results','second','failed')]
    reports=Reports(store)
    result={}
    for template in TEMPLATES:
        ident=template
        folder=store.home/'reports'/ident;folder.mkdir(parents=True);(folder/'figures').mkdir()
        manifest=reports.prepare(folder,flow,['results','second','failed','plan'],template)
        reports.jobs[ident]={'id':ident,'status':'preview','revision':flow['revision'],'_preparedFiles':{**manifest['files'],'manifest.json':sha((folder/'manifest.json').read_bytes())}}
        reports.build(ident,None,None,prepared=True)
        job=reports.status(ident)
        if job['status']!='ready':raise RuntimeError(job)
        extracted=destination/template
        with zipfile.ZipFile(folder/'source.zip') as bundle:bundle.extractall(extracted)
        # Use a separate copy: Quarto may clean an earlier output during rendering.
        replay=destination/(template+'-rerender');shutil.copytree(extracted,replay)
        # Re-render from the self-contained bundle; no application import is involved.
        subprocess.run(['quarto','render','report.qmd','--to','typst','--output','rerender.pdf','--no-execute'],cwd=replay,check=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180)
        result[template]={'folder':str(extracted),'pdfBytes':(extracted/'report.pdf').stat().st_size,'warnings':job['warnings']}
        print(template,flush=True)
    (destination/'report-template-check.json').write_text(json.dumps(result,indent=2)+'\n')
    print(destination/'report-template-check.json')


if __name__=='__main__':main()
