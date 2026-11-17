"""Selective review and explicit reconciliation preserve accepted history."""
import copy
from pathlib import Path
import tempfile
import unittest

from saigen.store import Store
from saigen.records import RecordError, Conflict
from saigen.reconstruction import propose, review, show


class ReconstructionReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.store=Store(self.root);self.store.init()
        (self.root/'chat.md').write_text('A filter was reported; the version is unknown.')
        (self.root/'log.txt').write_text('A different threshold was logged.')
        self.e={'source':'chat','location':'line 1','kind':'reported','note':'Version unknown'}
        self.spec={'id':'r','sources':{'chat':'chat.md'},'states':[{'id':'input','title':'Input','evidence':[self.e]},
                  {'id':'output','title':'Existing output','evidence':[self.e]}],
                  'connections':[{'from':['input'],'to':'output','label':'Reported filter','evidence':[self.e]}]}
        propose(self.store,self.spec,self.rev(),'Agent')
    def rev(self):return self.store.flow()['revision']
    def review(self,decision,**kwargs):return review(self.store,'r',decision,self.rev(),'Reviewer',**kwargs)

    def test_states_can_be_accepted_without_uncertain_relationship(self):
        with self.assertRaises(RecordError):self.review('accept',connection_id='r_0')
        self.review('accept',state_id='input')
        flow=self.review('accept',state_id='output')
        self.assertEqual(flow['reconstructions']['r']['status'],'partial')
        self.assertEqual(flow['actions'][0]['reconstruction']['review'],'draft')
        flow=self.review('reject',connection_id='r_0',reason='Conflicting threshold claims')
        self.assertEqual(flow['reconstructions']['r']['status'],'reviewed')
        self.assertEqual(len(flow['states']),2);self.assertFalse(flow['actions'])
        self.assertEqual(flow['reconstructions']['r']['archivedActions'][0]['reconstruction']['reviewReason'],'Conflicting threshold claims')
        self.assertIsNone(flow['states'][0]['performedBy'])

    def test_rejection_cascades_only_pending_incident_relationships(self):
        self.review('accept',state_id='input')
        flow=self.review('reject',state_id='output')
        self.assertEqual([n['id'] for n in flow['states']],['input'])
        self.assertEqual(flow['reconstructions']['r']['status'],'reviewed')
        graph=show(self.store,'r')['r']['graph']
        self.assertEqual(graph['source'],'mixed');self.assertEqual(len(graph['states']),2)
        with self.assertRaises(RecordError):self.review('reject',state_id='input')

    def test_whole_review_preserves_previously_accepted_items(self):
        self.review('accept',state_id='input')
        flow=self.review('reject')
        self.assertEqual(flow['states'][0]['reconstruction']['review'],'accepted')
        self.assertEqual(len(flow['reconstructions']['r']['archivedStates']),1)

    def extension(self):
        self.review('accept')
        return {'id':'later','sources':{'log':'log.txt'},'states':[],'connections':[],
                'relation':{'proposal':'r','kind':'extension','reason':'Later log contradicts the chat'},
                'existingStates':['input','output'],
                'addEvidence':[{'targetType':'action','targetId':'r_0','evidence':[
                    {'source':'log','location':'line 1','kind':'reported','note':'Different threshold'}]}]}

    def test_later_evidence_is_reviewed_and_additive(self):
        spec=self.extension();original=copy.deepcopy(self.store.flow()['actions'][0])
        propose(self.store,spec,self.rev(),'Agent')
        self.assertEqual(self.store.flow()['actions'][0],original)
        flow=review(self.store,'later','accept',self.rev(),'Reviewer',evidence_id='later_e0')
        action=flow['actions'][0]
        self.assertEqual(action['reconstruction'],original['reconstruction'])
        self.assertEqual(action['evidenceUpdates'][0]['evidence'][0]['note'],'Different threshold')
        again=copy.deepcopy(spec);again['id']='again'
        with self.assertRaises(RecordError):propose(self.store,again,self.rev(),'Agent')

    def test_extension_links_new_work_to_existing_nodes_without_duplication(self):
        spec=self.extension();spec['addEvidence']=[]
        e={'source':'log','location':'line 1','kind':'inferred','note':'New relation needs review'}
        spec['states']=[{'id':'new','title':'Additional result','evidence':[e]}]
        spec['connections']=[{'from':['output'],'to':'new','evidence':[e]}]
        propose(self.store,spec,self.rev(),'Agent')
        flow=review(self.store,'later','accept',self.rev(),'Reviewer')
        self.assertEqual(len(flow['states']),3);self.assertEqual(len(flow['actions']),2)
        self.assertEqual(flow['actions'][-1]['from'],['output'])
        self.assertEqual(flow['states'][1]['reconstruction']['id'],'r')

    def test_stale_or_invalid_evidence_review_does_not_mutate_target(self):
        spec=self.extension();propose(self.store,spec,self.rev(),'Agent')
        before=self.store.flow()
        with self.assertRaises(Conflict):review(self.store,'later','accept',-1,'Reviewer')
        self.assertEqual(self.store.flow(),before)
        flow=review(self.store,'later','reject',self.rev(),'Reviewer',evidence_id='later_e0')
        self.assertNotIn('evidenceUpdates',flow['actions'][0])

    def test_partial_reimport_does_not_silently_duplicate_preserved_state(self):
        (self.root/'result.csv').write_text('a,b\n1,2\n')
        spec=copy.deepcopy(self.spec);spec['id']='with_file';spec['states'][0].update(id='file_input',files=['result.csv'])
        spec['states'][1]['id']='file_output';spec['connections']=[]
        propose(self.store,spec,self.rev(),'Agent')
        again=copy.deepcopy(spec);again['id']='partial_copy';again['states'][0]['id']='duplicate'
        again['states'][1]['id']='different'
        again['states'].append({'id':'additional','title':'New state','evidence':[self.e]})
        with self.assertRaisesRegex(RecordError,'Existing evidence matches state'):
            propose(self.store,again,self.rev(),'Agent')
