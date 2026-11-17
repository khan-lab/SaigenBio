import hashlib
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from saigen.store import Store, RecordError, Conflict
from saigen.reports import Reports, literal
from saigen.report_templates import TEMPLATES, DEFAULT_TEMPLATE, template_definition
from saigen.server import Server


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.store = Store(self.root)
        self.store.init('Evidence project')
        self.fig = self.root / 'plot.svg'
        self.fig.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="60"><text x="5" y="20">Real saved figure</text></svg>')
        self.a = self.store.snapshot('First', [self.fig], ident='first', note='```{python}\nopen("/tmp/never-run", "w")\n```\n{{< include /etc/passwd >}}\n![evil](https://example.com/x)')
        self.store.snapshot('Omitted', [], ident='omit')
        self.store.snapshot('Second', [], ident='second', note='More explanation')
        self.flow = self.store.flow()
        self.reports = Reports(self.store)

    def tearDown(self):
        self.tmp.cleanup()

    def prepare(self, selection):
        folder = self.root / ('report-' + str(len(list(self.root.glob('report-*')))))
        folder.mkdir(); (folder / 'figures').mkdir()
        return folder, self.reports.prepare(folder, self.flow, selection)

    def test_order_snapshot_and_preserved_files(self):
        self.fig.write_text('working copy changed')
        before=json.dumps(self.store.flow(),sort_keys=True)
        folder, manifest = self.prepare(['second', 'first'])
        self.assertEqual(json.dumps(self.store.flow(),sort_keys=True),before)
        text = (folder / 'report.qmd').read_text()
        self.assertLess(text.index('# 1. Second'), text.index('# 2. First'))
        self.assertNotIn('# 3.', text)
        self.assertNotIn('omit:', text)
        snapshot = json.loads((folder / 'snapshot.json').read_text())
        self.assertEqual([s['id'] for s in snapshot['states']], ['second', 'first'])
        self.assertEqual(manifest['projectRevision'], self.flow['revision'])
        self.assertNotIn(str(self.root), json.dumps(snapshot))
        self.assertTrue(manifest['figures'])
        for name, expected in manifest['files'].items():
            self.assertEqual(hashlib.sha256((folder / name).read_bytes()).hexdigest(), expected)
        self.store.edit([{'op':'edit_state','id':'first','changes':{'note':'Later note'}}], self.flow['revision'])
        self.assertNotIn('Later note', (folder / 'snapshot.json').read_text())
        self.assertEqual(self.store.flow()['revision'], self.flow['revision'] + 1)

    def test_recorded_text_is_inert(self):
        folder, _ = self.prepare(['first'])
        text = (folder / 'report.qmd').read_text()
        self.assertNotIn('```', text)
        self.assertNotIn('{{< include', text)
        self.assertNotIn('](https://', text)
        self.assertIn('https\\:\\/\\/example\\.com\\/x', text)
        self.assertIn('enabled: false', text)
        self.assertEqual(literal('# heading'), '\\# heading')

    def test_explanations_and_sources_are_frozen_and_inert(self):
        from saigen.story import append
        notes=self.root/'chat.md';notes.write_text('A selected conversation excerpt.\n')
        source=self.store.snapshot('Source',[notes],ident='notes')
        aid=source['artifactIds'][0]
        append(self.store,{'kind':'decision','states':['first'],'summary':'```{python}\nraise SystemExit()\n```',
                          'rationale':'Keep original evidence','agreementBasis':'Not established',
                          'evidence':[{'type':'artifact','id':aid,'location':'line 1'}]},self.store.flow()['revision'],'Agent')
        self.flow=self.store.flow();before=json.dumps(self.flow,sort_keys=True)
        notes.write_text('Changed working copy')
        folder,manifest=self.prepare(['first'])
        snapshot=json.loads((folder/'snapshot.json').read_text())
        self.assertEqual(snapshot['explanations'][0]['recordedBy'],'Agent')
        self.assertIn(aid,snapshot['evidenceFiles'])
        self.assertEqual((folder/snapshot['evidenceFiles'][aid]).read_text(),'A selected conversation excerpt.\n')
        self.assertNotIn('```{python}',(folder/'report.qmd').read_text())
        self.assertEqual(json.dumps(self.store.flow(),sort_keys=True),before)
        for name,expected in manifest['files'].items():
            self.assertEqual(hashlib.sha256((folder/name).read_bytes()).hexdigest(),expected)

    def test_planned_result_explanation_is_exported(self):
        self.store.plan('QC summary',['first'],'QC plots.',ident='qc',
                        details='Inspect counts.',requires='Review inputs.')
        self.store.plan('Legacy plan',['first'],'Expected: old explanation',ident='legacy')
        def legacy(f):
            n=next(n for n in f['states'] if n['id']=='legacy')
            n['note']=n['expectedSummary']
            n.pop('planDetails');n.pop('planRequires')
            return {},None
        self.store.update('test.legacy','Test',legacy)
        self.flow=self.store.flow()
        folder,_=self.prepare(['qc','legacy'])
        text=(folder/'report.qmd').read_text()
        self.assertIn('Expected result: '+literal('QC plots.'),text)
        self.assertIn('Proposed method: '+literal('Inspect counts.'),text)
        self.assertIn(literal('Review inputs.'),text)
        self.assertEqual(text.count(literal('Expected: old explanation')),1)
        snapshot=json.loads((folder/'snapshot.json').read_text())
        self.assertEqual(snapshot['states'][0]['planDetails'],'Inspect counts.')

    def test_missing_and_unsafe_figures_are_honest(self):
        ar = self.flow['artifacts'][self.a['artifactIds'][0]]
        self.store.artifact_path(ar).unlink()
        folder, manifest = self.prepare(['first'])
        self.assertFalse(manifest['figures'])
        self.assertIn('Figure unavailable:', (folder / 'report.qmd').read_text())
        self.assertTrue(manifest['warnings'])
        self.fig.write_text('<svg xmlns="http://www.w3.org/2000/svg"><image href="file:///etc/passwd"/></svg>')
        state = self.store.snapshot('Unsafe', [self.fig], ident='unsafe')
        self.flow = self.store.flow()
        _, manifest = self.prepare(['unsafe'])
        self.assertFalse(manifest['figures'])
        self.assertIn('unsupported', manifest['warnings'][0])

    def test_command_aliases_retain_options(self):
        self.flow['actions'] = [{'id':'action','to':'first','from':['omit'],'status':'completed','label':'Plot','argv':['/opt/tools/python3','/Users/example/project/plot.py','plot','--input','/Users/example/project/counts.tsv','--scale','linear']}]
        folder, _ = self.prepare(['first'])
        text = (folder / 'report.qmd').read_text()
        self.assertIn('python3', text)
        self.assertIn('plot.py', text)
        self.assertIn('scale linear', text)
        self.assertNotIn('/Users/example', text)

    def test_notebook_scripts_tables_and_reuse(self):
        script = self.root / 'analysis.py'
        original = 'print("preserved original")\n```\n{{< include /etc/passwd >}}'
        script.write_text(original)
        ar = self.store.capture(script, role='code')
        self.flow['artifacts'][ar['id']] = ar
        self.flow['actions'] = [dict(id='a'+target, to=target, **{'from':[]},
            status='completed', reason='More explanation', argv=['python', 'analysis.py'],
            code={'scriptArtifacts':[ar['id']]}) for target in ['second', 'first']]
        script.write_text('changed working copy')
        table = self.root / 'counts.tsv'
        table.write_text('sample\tcount\na\t3\nb\t5\n')
        record = self.store.capture(table, role='output')
        self.flow['artifacts'][record['id']] = record
        self.flow['states'][2]['artifactIds'].append(record['id'])
        folder, _ = self.prepare(['second', 'first'])
        source = (folder / 'report.qmd').read_text()
        self.assertEqual(source.count('preserved original'), 1)
        self.assertNotIn('changed working copy', source)
        self.assertIn('shown in section 1', source)
        self.assertIn('````python', source)
        self.assertNotIn('```{python}', source)
        self.assertIn('| sample | count |', source)
        self.assertIn('Saved table preview', source)
        self.assertEqual(source.count('More explanation'), 2)  # one per state
        self.assertNotIn('pagebreak', source)
        self.assertLess(source.index('preserved original'), source.index('python analysis.py'))
        self.assertLess(source.index('python analysis.py'), source.index('| sample | count |'))
        self.store.artifact_path(ar).chmod(0o600)
        self.store.artifact_path(ar).write_text('tampered')
        _, manifest = self.prepare(['second'])
        self.assertTrue(any('changed' in w or 'hash mismatch' in w for w in manifest['warnings']))

    def test_changed_script_versions_are_both_displayed(self):
        script = self.root / 'analysis.py'
        self.flow['actions'] = []
        for target, contents in [('first', 'print("version one")'), ('second', 'print("version two")')]:
            script.write_text(contents)
            ar = self.store.capture(script, role='code')
            self.flow['artifacts'][ar['id']] = ar
            self.flow['actions'].append({'id':'a'+target, 'to':target, 'from':[],
                'status':'completed', 'argv':['python', 'analysis.py'],
                'code':{'scriptArtifacts':[ar['id']]}})
        folder, _ = self.prepare(['first', 'second'])
        source = (folder / 'report.qmd').read_text()
        self.assertIn('print("version one")', source)
        self.assertIn('print("version two")', source)
        self.assertNotIn('shown in section', source)

    def test_selection_validation(self):
        for selection in [[], ['first','first'], ['missing'], 'first']:
            with self.assertRaises(RecordError): self.reports.start(selection, self.flow['revision'])
        with self.assertRaises(Conflict): self.reports.start(['first'], -1)
        with self.assertRaises(RecordError): self.reports.file('../etc/passwd', 'pdf')

    def test_fixed_render_command_and_failure(self):
        folder = self.store.home / 'reports' / 'test'
        self.reports.jobs['test'] = {'id':'test','status':'queued'}
        with patch('saigen.reports.shutil.which', return_value='/usr/local/bin/quarto'), patch('saigen.reports.subprocess.run') as run:
            run.return_value.returncode = 1
            run.return_value.stdout = b'failure'
            self.reports.build('test', self.flow, ['first'])
            self.assertEqual(run.call_args.args[0], ['/usr/local/bin/quarto', 'render','report.qmd','--to','typst','--output','report.pdf','--no-execute'])
            self.assertEqual(run.call_args.kwargs['cwd'], folder)
            self.assertNotIn('shell', run.call_args.kwargs)
        self.assertEqual(self.reports.status('test')['status'], 'failed')
        self.assertEqual(self.reports.file('test', 'log').read_bytes(), b'failure')
        with self.assertRaises(RecordError): self.reports.file('test', 'pdf')
        self.assertEqual(self.store.flow()['revision'], self.flow['revision'])

    def test_backend_phases_and_preparation_failure_log(self):
        self.reports.jobs['phases'] = {'id':'phases','status':'queued'}
        observed=[]
        original_prepare=self.reports.prepare
        def prepare(*args):
            observed.append(self.reports.status('phases')['status'])
            return original_prepare(*args)
        def command(argv, **kwargs):
            from types import SimpleNamespace
            observed.append(self.reports.status('phases')['status'])
            return SimpleNamespace(returncode=1, stdout=b'Quarto failure')
        with patch.object(self.reports,'prepare',side_effect=prepare), patch('saigen.reports.shutil.which',return_value='quarto'), patch('saigen.reports.subprocess.run',side_effect=command):
            self.reports.build('phases',self.flow,['first'])
        self.assertEqual(observed,['preparing','preparing','rendering'])
        self.reports.jobs['missing']={'id':'missing','status':'queued'}
        with patch('saigen.reports.shutil.which',return_value=None):
            self.reports.build('missing',self.flow,['first'])
        self.assertIn('Quarto is unavailable',self.reports.file('missing','log').read_text())

    def test_inclusion_issue_attached_to_affected_result(self):
        artifact=self.flow['artifacts'][self.a['artifactIds'][0]]
        self.store.artifact_path(artifact).unlink()
        folder,manifest=self.prepare(['first','second'])
        self.assertIn('Figure unavailable',manifest['outline'][0]['inclusionIssues'][0])
        self.assertEqual(manifest['outline'][1]['inclusionIssues'],[])
        self.assertTrue(manifest['warnings'])

    def test_template_variants_share_evidence_and_bundle_identity(self):
        script = self.root / 'method.py'; script.write_text('print("full source marker")\nprint("selected line")\n')
        ar = self.store.capture(script, role='code')
        self.flow['artifacts'][ar['id']] = ar
        self.flow['actions'] = [{'id':'a','to':'second','from':['first'],'status':'completed',
            'argv':['python','method.py'], 'environment':{'declaredToolVersions':['Python 3']},
            'code':{'scriptArtifacts':[ar['id']], 'explanation':{'summary':'Explain a method', 'recordedBy':'Agent',
                'excerpts':[{'artifactId':ar['id'],'start':2,'end':2,'text':'print("selected line")'}]}}}]
        snapshots=[]; inventories=[]
        for template in TEMPLATES:
            folder=self.root/template;folder.mkdir();(folder/'figures').mkdir()
            manifest=self.reports.prepare(folder,self.flow,['second','first'],template)
            source=(folder/'report.qmd').read_text()
            snapshots.append((folder/'snapshot.json').read_bytes());inventories.append(manifest['artifacts'])
            self.assertEqual(manifest['template'],template_definition(template))
            self.assertEqual(json.loads((folder/'report-template.json').read_text()),manifest['template'])
            self.assertIn('enabled: false',source)
            self.assertIn('Explain a method',source)
            if template=='results-summary':
                self.assertNotIn('python method.py',source)
                self.assertNotIn('selected line',source)
            elif template=='analysis-notebook':
                self.assertIn('selected line',source)
                self.assertNotIn('full source marker',source)
                self.assertIn('Excerpt selected by Agent',source)
            else:
                self.assertIn('full source marker',source)
                self.assertIn('Python 3',source)
                self.assertIn('SHA',source)
        self.assertEqual(snapshots[0],snapshots[1]);self.assertEqual(snapshots[1],snapshots[2])
        self.assertEqual(inventories[0],inventories[2])
        self.assertEqual(DEFAULT_TEMPLATE,'analysis-notebook')
        with self.assertRaises(RecordError):self.reports.preview(['first'],self.flow['revision'],'../../evil')

    def test_preview_does_not_render_and_export_keeps_reviewed_snapshot(self):
        with patch('saigen.reports.subprocess.run') as command:
            preview=self.reports.preview(['second','first'],self.flow['revision'],'results-summary')
            command.assert_not_called()
        folder=self.store.home/'reports'/preview['id']
        source=(folder/'report.qmd').read_bytes()
        snapshot=(folder/'snapshot.json').read_bytes()
        self.store.edit([{'op':'edit_state','id':'second','changes':{'note':'Changed after preview'}}],self.flow['revision'])
        with self.assertRaises(Conflict):self.reports.render_preview(preview['id'],-1)
        def render(argv,**kw):
            if 'render' in argv:(folder/'report.pdf').write_bytes(b'%PDF-test')
            from subprocess import CompletedProcess
            return CompletedProcess(argv,0,b'quarto version test')
        with patch('saigen.reports.shutil.which',return_value='/tool/quarto'),patch('saigen.reports.subprocess.run',side_effect=render):
            # Call the same prepared-build path synchronously for deterministic assertions.
            self.reports.build(preview['id'],None,None,prepared=True)
        self.assertEqual(self.reports.status(preview['id'])['status'],'ready')
        self.assertEqual((folder/'report.qmd').read_bytes(),source)
        self.assertEqual((folder/'snapshot.json').read_bytes(),snapshot)
        import zipfile
        with zipfile.ZipFile(folder/'source.zip') as bundle:
            self.assertIn('report-template.json',bundle.namelist())
            self.assertEqual(bundle.read('snapshot.json'),snapshot)
        with self.assertRaises(RecordError):self.reports.render_preview(preview['id'],preview['revision'])

    def test_notebook_does_not_reference_full_source_that_only_had_an_excerpt(self):
        script=self.root/'method.py';script.write_text('print("full marker")\nprint("excerpt marker")\n')
        ar=self.store.capture(script,role='code');self.flow['artifacts'][ar['id']]=ar
        self.flow['actions']=[{'id':target,'to':target,'from':[],'status':'completed',
            'code':{'scriptArtifacts':[ar['id']], **({'explanation':{'recordedBy':'Agent','excerpts':[{'artifactId':ar['id'],'start':2,'end':2,'text':'print("excerpt marker")'}]}} if target=='first' else {})}}
            for target in ('first','second')]
        folder,_=self.prepare(['first','second'])
        source=(folder/'report.qmd').read_text()
        second=source.split('# 2. Second')[1]
        self.assertIn('full marker',second)
        self.assertNotIn('shown in section 1',second)

    def test_changed_preview_source_is_not_rendered(self):
        preview=self.reports.preview(['first'],self.flow['revision'])
        folder=self.store.home/'reports'/preview['id']
        (folder/'report.qmd').write_text('changed after preview')
        with patch('saigen.reports.subprocess.run') as command:
            self.reports.build(preview['id'],None,None,prepared=True)
            command.assert_not_called()
        self.assertEqual(self.reports.status(preview['id'])['status'],'failed')
        self.assertIn('changed',self.reports.status(preview['id'])['error'])
        self.assertNotIn('_preparedFiles',preview)

    def test_all_templates_keep_status_warnings_and_inert_text(self):
        self.flow['states'][0]['status']='failed'
        ar=self.flow['artifacts'][self.a['artifactIds'][0]]
        self.store.artifact_path(ar).unlink()
        for template in TEMPLATES:
            folder=self.root/template;folder.mkdir();(folder/'figures').mkdir()
            manifest=self.reports.prepare(folder,self.flow,['first'],template)
            source=(folder/'report.qmd').read_text()
            self.assertIn('failed',source)
            self.assertIn('Figure unavailable',source)
            self.assertNotIn('```{python}',source)
            self.assertNotIn('{{< include',source)
            self.assertTrue(manifest['warnings'])

    def test_http_protection(self):
        server = Server(('127.0.0.1',0), self.store)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        base = 'http://127.0.0.1:' + str(server.server_port)
        def call(path, body=None, headers=None):
            return urlopen(Request(base + path, data=json.dumps(body).encode() if body else None, headers=headers or {}))
        try:
            for suffix in ['/api/reports/guess','/api/reports/guess/pdf','/api/reports/guess/log','/api/reports/../project.sqlite/pdf']:
                with self.assertRaises(HTTPError) as ctx: call(suffix)
                self.assertEqual(ctx.exception.code,403)
            folder=self.store.home/'reports'/'failure';folder.mkdir(parents=True)
            (folder/'render.log').write_text('Render failure details')
            server.reports.jobs['failure']={'id':'failure','status':'failed'}
            with call('/api/reports/failure/log', headers={'X-Saigen-Token':server.token}) as response:
                self.assertEqual(response.read(),b'Render failure details')
                self.assertEqual(response.headers.get_content_type(),'text/plain')
            headers={'X-Saigen-Token':server.token,'Content-Type':'application/json'}
            with self.assertRaises(HTTPError) as ctx: call('/api/reports', {'revision':self.flow['revision'],'selected':['first']}, dict(headers, Origin='https://example.com'))
            self.assertEqual(ctx.exception.code,403)
            with patch.object(server.reports,'start',return_value={'id':'safe','status':'queued'}) as start:
                with call('/api/reports', {'revision':self.flow['revision'],'selected':['second','first']}, headers) as response:
                    self.assertEqual(response.status,202)
                start.assert_called_once_with(['second','first'], self.flow['revision'])
            with self.assertRaises(HTTPError) as ctx:
                call('/api/reports/preview', {'revision':self.flow['revision'],'selected':['first'],'template':'unknown'},headers)
            self.assertEqual(ctx.exception.code,400)
            with call('/api/reports/preview', {'revision':self.flow['revision'],'selected':['first'],'template':'results-summary'},headers) as response:
                preview=json.load(response)
            self.assertEqual(preview['status'],'preview')
            with self.assertRaises(HTTPError) as ctx:
                call('/api/reports/'+preview['id']+'/render',{'revision':-1},headers)
            self.assertEqual(ctx.exception.code,409)
            built=threading.Event()
            with patch.object(server.reports,'build',side_effect=lambda *args:built.set()) as build:
                with call('/api/reports/'+preview['id']+'/render',{'revision':preview['revision']},headers) as response:
                    self.assertEqual(response.status,202)
                # The build thread consumes the prepared snapshot, not a fresh graph read.
                self.assertTrue(built.wait(2))
                self.assertTrue(build.call_args.args[-1])
        finally:
            server.shutdown(); server.server_close(); thread.join()

if __name__ == '__main__': unittest.main()
