import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from saigen.store import Store, RecordError, Conflict
from saigen.reconstruction import propose, review, setup_context
from saigen.runner import run

class ReconstructionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.store=Store(self.root);self.store.init('Existing')
        (self.root/'chat.md').write_text('Reported filter; execution version unknown.')
        (self.root/'result.csv').write_text('a,b\n1,2\n')
        self.evidence={'source':'chat','location':'line 1','kind':'reported','note':'Reported, not observed'}
        self.spec={'id':'r1','sources':{'chat':'chat.md'},'states':[{'id':'old','title':'Existing result','files':['result.csv'],'evidence':[self.evidence]}],'connections':[]}
    def publish(self):return propose(self.store,self.spec,self.store.flow()['revision'],'Agent')
    def test_setup_only_references_selected_files(self):
        context=setup_context(self.root,'.',['chat.md'])
        self.assertEqual(context['sources'],[str((self.root/'chat.md').resolve())])
        self.assertFalse(self.store.flow()['states'])
    def test_preservation_review_and_new_run(self):
        flow=self.publish();node=flow['states'][0]
        (self.root/'chat.md').write_text('changed')
        source=self.store.artifact(node['reconstruction']['evidence'][0]['artifactId'])
        self.assertIn('Reported filter',self.store.artifact_path(source).read_text())
        with self.assertRaises(RecordError):run(self.store,['old'],'Attempt',['echo','test'])
        flow=review(self.store,'r1','accept',flow['revision'],'Human')
        self.assertEqual(flow['states'][0]['origin'],'reconstructed')
        self.assertIsNone(flow['states'][0]['performedBy'])
        result=run(self.store,['old'],'New observed attempt',['/bin/echo','Synthetic test'])
        self.assertEqual(result['status'],'completed')
        self.assertEqual(len(self.store.flow()['states']),2)
    def test_reject_archives_and_duplicate_rejected(self):
        flow=self.publish()
        with self.assertRaises(RecordError):self.publish()
        with self.assertRaises(Conflict):review(self.store,'r1','accept',-1,'Human')
        flow=review(self.store,'r1','reject',flow['revision'],'Human')
        self.assertFalse(flow['states'])
        self.assertEqual(flow['reconstructions']['r1']['archivedStates'][0]['id'],'old')
        spec=copy.deepcopy(self.spec);spec['id']='r2'
        with self.assertRaises(RecordError):propose(self.store,spec,flow['revision'],'Agent')
    def test_invalid_evidence_and_cycle_are_atomic(self):
        spec=copy.deepcopy(self.spec);spec['states'][0]['evidence'][0]['source']='missing'
        with self.assertRaises(RecordError):propose(self.store,spec,self.store.flow()['revision'],'Agent')
        self.assertFalse(self.store.flow()['states'])
        self.spec['connections']=[{'from':['old'],'to':'old','evidence':[self.evidence]}]
        with self.assertRaises(RecordError):self.publish()
        self.assertFalse(self.store.flow()['states'])

    def test_init_records_context_without_importing(self):
        import contextlib, io, json
        from saigen.onboarding import initialize
        workspace=self.root/'separate';store=Store(workspace)
        with contextlib.redirect_stdout(io.StringIO()):
            initialize(store,name='Reconstruction',agents=['codex'],non_interactive=True,existing_project=str(self.root),history_files=[str(self.root/'chat.md')])
        config=json.loads((workspace/'saigen-workspace.json').read_text())
        self.assertEqual(config['reconstruction']['directory'],str(self.root.resolve()))
        self.assertFalse(store.flow()['states'])
        self.assertTrue((workspace/'.agents/skills/saigen-record/references/reconstruction.md').is_file())
