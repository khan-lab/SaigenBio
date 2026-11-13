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
        folder, manifest = self.prepare(['second', 'first'])
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
        self.assertEqual(self.store.flow()['revision'], self.flow['revision'])

    def test_http_protection(self):
        server = Server(('127.0.0.1',0), self.store)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        base = 'http://127.0.0.1:' + str(server.server_port)
        def call(path, body=None, headers=None):
            return urlopen(Request(base + path, data=json.dumps(body).encode() if body else None, headers=headers or {}))
        try:
            for suffix in ['/api/reports/guess','/api/reports/guess/pdf','/api/reports/../project.sqlite/pdf']:
                with self.assertRaises(HTTPError) as ctx: call(suffix)
                self.assertEqual(ctx.exception.code,403)
            headers={'X-Saigen-Token':server.token,'Content-Type':'application/json'}
            with self.assertRaises(HTTPError) as ctx: call('/api/reports', {'revision':self.flow['revision'],'selected':['first']}, dict(headers, Origin='https://example.com'))
            self.assertEqual(ctx.exception.code,403)
            with patch.object(server.reports,'start',return_value={'id':'safe','status':'queued'}) as start:
                with call('/api/reports', {'revision':self.flow['revision'],'selected':['second','first']}, headers) as response:
                    self.assertEqual(response.status,202)
                start.assert_called_once_with(['second','first'], self.flow['revision'])
        finally:
            server.shutdown(); server.server_close(); thread.join()

if __name__ == '__main__': unittest.main()
