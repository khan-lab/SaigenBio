"""Synthetic verification runs preserve originals and record explicit comparison limits."""
import copy
import csv
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from unittest.mock import patch

from saigen.comparison import compare
from saigen.records import RecordError, Conflict
from saigen.store import Store
from saigen import verification as v


class VerificationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.store=Store(self.root);self.store.init()
        source=self.root/'input.csv';source.write_text('sample,value\nA,1.0\nB,2.0\n')
        original=self.root/'original.csv';original.write_text('sample,value\nA,1.0\nB,2.0\n')
        self.input=self.store.snapshot('Input',[source],ident='input')
        self.original=self.store.snapshot('Original',[original],ident='original')
        self.aid=self.original['artifactIds'][0]
        self.spec={'originalStateId':'original','inputStateIds':['input'],'inputArtifactIds':self.input['artifactIds'],
                   'codeArtifactIds':[],'command':[sys.executable,'-c','from pathlib import Path; import shutil; shutil.copyfile("{input:0}","result.csv")'],
                   'outputs':['result.csv'],'criteria':[{'originalArtifactId':self.aid,'output':'result.csv','method':'sha256'}],
                   'reason':'Check exact reproduction','prerequisites':'Python standard library only','resources':'Local synthetic fixture; no network or paid compute'}
    def rev(self):return self.store.flow()['revision']
    def propose(self,spec=None):
        flow=v.propose(self.store,spec or self.spec,self.rev(),'Agent')
        return list(flow['verifications']['proposals'].values())[-1]
    def approve(self,p):return v.approve(self.store,p['id'],p['digest'],self.rev(),'Approval recorder')

    def test_no_execution_before_matching_revision_and_approval(self):
        p=self.propose()
        with patch('saigen.verification.run') as run:
            with self.assertRaises(RecordError):v.execute(self.store,p['id'],self.rev())
            with self.assertRaises(RecordError):v.approve(self.store,p['id'],'wrong',self.rev())
            self.approve(p)
            with self.assertRaises(Conflict):v.execute(self.store,p['id'],-1)
            run.assert_not_called()
        self.assertEqual(len(self.store.flow()['states']),2)

    def test_exact_match_creates_separate_attempt_and_comparison(self):
        before=copy.deepcopy(self.store.flow()['states'][1]);body=(self.root/'original.csv').read_bytes()
        p=self.propose();self.approve(p)
        flow=v.execute(self.store,p['id'],self.rev(),'Runner')
        attempt=next(iter(flow['verifications']['attempts'].values()))
        self.assertEqual(attempt['comparisonStatus'],'match')
        self.assertEqual(flow['states'][1],before)
        self.assertEqual((self.root/'original.csv').read_bytes(),body)
        self.assertEqual(len(flow['states']),4)
        comparison=next(n for n in flow['states'] if n['id']==attempt['comparisonStateId'])
        self.assertEqual(comparison['verificationComparison']['status'],'match')
        self.assertIn(attempt['stateId'],flow['actions'][-1]['from'])
        revision=self.rev();v.compare(self.store,attempt['id'],revision)
        self.assertEqual(self.rev(),revision)
        v.execute(self.store,p['id'],self.rev(),'Runner')
        self.assertEqual(len(self.store.flow()['verifications']['attempts']),2)

    def test_numeric_match_does_not_hide_byte_difference(self):
        spec=copy.deepcopy(self.spec)
        spec['command']=[sys.executable,'-c','from pathlib import Path; Path("result.csv").write_text("sample,value\\nB,2.000001\\nA,1.0\\n")']
        spec['criteria'].append({'originalArtifactId':self.aid,'output':'result.csv','method':'numeric-table',
                                 'keyColumns':['sample'],'columns':['value'],'atol':0.00001,'rtol':0})
        p=self.propose(spec);self.approve(p);flow=v.execute(self.store,p['id'],self.rev())
        report=flow['states'][-1]['verificationComparison']
        self.assertEqual(report['status'],'partial')
        self.assertEqual([r['status'] for r in report['criteria']],['different','match'])

    def test_failed_command_remains_failed_even_if_an_output_matches(self):
        spec=copy.deepcopy(self.spec);spec['command'][-1]+='; raise SystemExit(1)'
        p=self.propose(spec);self.approve(p);flow=v.execute(self.store,p['id'],self.rev())
        self.assertEqual(flow['states'][-2]['status'],'failed')
        self.assertEqual(flow['states'][-1]['verificationComparison']['status'],'failed')
        self.assertEqual(flow['states'][-1]['verificationComparison']['criteria'][0]['status'],'match')

    def test_missing_outputs_and_invalid_numbers_are_not_matches(self):
        spec=copy.deepcopy(self.spec);spec['command']=[sys.executable,'-c','pass']
        p=self.propose(spec);self.approve(p);flow=v.execute(self.store,p['id'],self.rev())
        self.assertEqual(flow['states'][-1]['verificationComparison']['criteria'][0]['status'],'unavailable')
        left=self.root/'left.csv';right=self.root/'right.csv'
        left.write_text('key,value\nA,1\n');right.write_text('key,value\nA,NaN\n')
        criterion={'method':'numeric-table','keyColumns':['key'],'columns':['value'],'atol':0,'rtol':0}
        with self.assertRaises(RecordError):compare(left,right,criterion)
        right.write_text('key,value\nA,1\nA,1\n')
        with self.assertRaises(RecordError):compare(left,right,criterion)

    def test_numeric_criteria_report_missing_rows_and_uncompared_columns(self):
        left=self.root/'left.csv';right=self.root/'right.csv'
        left.write_text('key,value,note\nA,1,old\nB,2,old\n');right.write_text('key,value,note\nA,1,new\nC,2,new\n')
        result=compare(left,right,{'method':'numeric-table','keyColumns':['key'],'columns':['value'],'atol':0,'rtol':0})
        self.assertEqual(result['status'],'different');self.assertEqual(result['missingKeyCount'],1)
        self.assertEqual(result['addedKeyCount'],1);self.assertEqual(result['uncomparedOriginalColumns'],['note'])

    def test_runtime_and_code_are_pinned_and_cancel_blocks_execution(self):
        spec=copy.deepcopy(self.spec);spec['command']=[sys.executable,str(self.root/'mutable.py')]
        with self.assertRaises(RecordError):self.propose(spec)
        p=self.propose();self.approve(p)
        v.cancel(self.store,p['id'],'Use another procedure',self.rev())
        with patch('saigen.verification.run') as run:
            with self.assertRaises(RecordError):v.execute(self.store,p['id'],self.rev())
            run.assert_not_called()

    def test_preserved_code_is_used_after_working_script_changes(self):
        script=self.root/'copy.py';script.write_text('import shutil\nshutil.copyfile(__import__("sys").argv[1],"result.csv")\n')
        code=self.store.snapshot('Code evidence',[script],ident='code')
        spec=copy.deepcopy(self.spec);spec['codeArtifactIds']=code['artifactIds']
        spec['command']=[sys.executable,'{code:0}','{input:0}']
        p=self.propose(spec);self.approve(p)
        script.write_text('raise SystemExit("Changed working code must not execute")')
        flow=v.execute(self.store,p['id'],self.rev())
        self.assertEqual(flow['states'][-1]['verificationComparison']['status'],'match')

    def test_changed_preserved_artifact_blocks_launch(self):
        p=self.propose();self.approve(p)
        path=self.store.artifact_path(self.store.artifact(self.input['artifactIds'][0]))
        path.chmod(0o600)  # Simulate external corruption of an intentionally read-only object.
        path.write_text('tampered')
        before=self.store.flow()
        with patch('saigen.verification.run') as run:
            with self.assertRaises(RecordError):v.execute(self.store,p['id'],self.rev())
            run.assert_not_called()
        self.assertEqual(self.store.flow(),before)

    def test_invalid_criteria_and_missing_evidence_are_atomic(self):
        for change in ({'inputArtifactIds':['missing']},{'criteria':[]},{'command':[]},
                       {'criteria':[{'originalArtifactId':self.aid,'output':'result.csv','method':'semantic'}]}):
            spec={**self.spec,**change};before=self.store.flow()
            with self.assertRaises(RecordError):self.propose(spec)
            self.assertEqual(self.store.flow(),before)

    def test_recover_lost_supervisor_never_infers_success(self):
        p=self.propose();self.approve(p)
        with patch('saigen.verification.run',side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):v.execute(self.store,p['id'],self.rev())
        attempt=next(iter(self.store.flow()['verifications']['attempts'].values()))
        with patch('saigen.verification.os.kill',side_effect=ProcessLookupError):
            flow=v.recover(self.store,attempt['id'],self.rev())
        self.assertEqual(flow['verifications']['attempts'][attempt['id']]['status'],'unknown')
        with self.assertRaises(RecordError):v.compare(self.store,attempt['id'],self.rev())
        # Unknown preparation does not overwrite originals and permits a separate retry.
        flow=v.execute(self.store,p['id'],self.rev())
        self.assertEqual(len(flow['verifications']['attempts']),2)

    def test_http_approval_records_agreement_without_launching(self):
        from saigen.server import Server
        p=self.propose();server=Server(('127.0.0.1',0),self.store)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        self.addCleanup(lambda:(server.shutdown(),server.server_close(),thread.join()))
        url=f'http://127.0.0.1:{server.server_port}/api/verifications/{p["id"]}/approve'
        def request(token,revision):
            return urllib.request.urlopen(urllib.request.Request(url,json.dumps({'digest':p['digest'],'revision':revision}).encode(),
                {'Content-Type':'application/json','X-Saigen-Token':token}))
        before=self.rev()
        with self.assertRaises(urllib.error.HTTPError) as error:request('wrong',before)
        self.assertEqual(error.exception.code,403)
        with patch('saigen.verification.run') as run:
            with request(server.token,before) as response:self.assertEqual(response.status,200)
            run.assert_not_called()
        with self.assertRaises(urllib.error.HTTPError) as error:request(server.token,before)
        self.assertEqual(error.exception.code,409)
        self.assertFalse(self.store.flow()['verifications']['attempts'])
