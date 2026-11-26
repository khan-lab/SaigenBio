"""Decision context survives execution, corrections, archives and session changes."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

from saigen.records import RecordError, Conflict
from saigen.state_archive import set_archived
from saigen.store import Store
from saigen.story import append, read, archive_index
from saigen.server import Server
from saigen.workflows.service import WorkflowService


class StoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = Store(self.root)
        self.store.init('Synthetic story')
        self.store.snapshot('Input', [], ident='input')
        self.store.plan('Initial plan', ['input'], 'Expected table', actor='Proposer', ident='plan')
        self.decision = {'kind':'decision', 'states':['plan'], 'summary':'Use a small threshold',
                         'rationale':'Keep weak signals for inspection',
                         'alternatives':[{'option':'Higher threshold','reason':'Would remove weak signals'}],
                         'agreementBasis':'Researcher requested this exploratory comparison',
                         'participants':[{'name':'Researcher','role':'approver'}],
                         'evidence':[{'type':'state','id':'input','location':'Starting evidence'}]}

    def add(self, entry=None, actor='Agent'):
        return append(self.store, entry or self.decision, self.store.flow()['revision'], actor)

    def test_plan_running_failed_retry_and_context_preservation(self):
        self.add()
        self.store.edit([{'op':'edit_state','id':'plan','changes':{'title':'Revised plan'}}], self.store.flow()['revision'], 'Researcher')
        aid, sid = self.store.begin('Attempt', ['input'], ['synthetic'], 'Runner', 'Exploratory run', [], [], {}, {}, planned='plan')
        story = read(self.store, sid)
        self.assertEqual(story['state']['status'], 'running')
        self.assertEqual(story['state']['plan']['writtenBy'], 'Proposer')
        self.assertEqual(story['originalPlan']['title'], 'Initial plan')
        self.assertEqual(story['entries'][0]['rationale'], self.decision['rationale'])
        self.assertTrue(any(p['name']=='Researcher' and p['role']=='Approver' for p in story['participants']))
        self.assertFalse(any(p['name']=='Runner' and 'approv' in p['role'].lower() for p in story['participants']))
        self.store.finish(aid, 'failed', 1, [], [], 'Synthetic failure')
        self.assertEqual(read(self.store, sid)['state']['status'], 'failed')
        retry, retry_id = self.store.begin('Retry', ['input'], ['synthetic'], 'Runner', '', [], [], {}, {}, ident='retry')
        self.store.finish(retry, 'completed', 0, [], [])
        self.add({'kind':'replacement','states':['plan'],'summary':'Retry after the failed attempt','replacementStateId':retry_id})
        self.assertEqual(read(self.store, 'plan')['state']['status'], 'failed')
        self.assertEqual(read(self.store, retry_id)['replacements'][0]['states'], ['plan'])
        self.assertEqual(len(read(Store(self.root), 'plan')['entries']), 2)

    def test_append_only_corrections_and_revision_guards(self):
        flow = self.add()
        first = next(iter(flow['explanations'].values()))
        corrected = {**self.decision, 'summary':'Corrected decision', 'supersedes':first['id']}
        with self.assertRaises(Conflict):
            append(self.store, corrected, -1, 'Human')
        self.add(corrected, 'Human')
        entries = read(self.store, 'plan')['entries']
        self.assertEqual(entries[0]['summary'], self.decision['summary'])
        self.assertEqual(entries[0]['supersededBy'], entries[1]['id'])
        self.assertEqual(entries[1]['recordedBy'], 'Human')
        with self.assertRaises(RecordError):
            self.add(corrected)

    def test_invalid_documents_are_atomic(self):
        variants = [None, {}, {**self.decision,'participants':None}, {**self.decision,'evidenceKind':[]},
                    {**self.decision,'states':['missing']}, {**self.decision,'actions':['missing']},
                    {**self.decision,'evidence':[{'type':'artifact','id':'missing','location':'line 1'}]},
                    {**self.decision,'historicalAt':'2020-01-01'},
                    {**self.decision,'participants':[{'name':'X','role':'authenticated'}]},
                    {**self.decision,'supersedes':'missing'}]
        for entry in variants:
            before = self.store.flow()
            with self.subTest(entry=entry), self.assertRaises(RecordError):
                append(self.store, entry, before['revision'])
            self.assertEqual(self.store.flow(), before)

    def test_reported_historical_time_is_not_recording_time(self):
        self.add({**self.decision,'historicalAt':'2020-02-01T10:00:00Z','evidenceKind':'inferred'})
        story = read(self.store, 'plan')
        self.assertEqual(story['entries'][0]['historicalAt'], '2020-02-01T10:00:00Z')
        self.assertNotEqual(story['timeline'][-1]['at'], story['entries'][0]['historicalAt'])

    def test_layout_edits_do_not_reassign_annotation_authorship(self):
        self.store.edit([{'op':'edit_state','id':'plan','changes':{'note':'My reasoning'}}], self.store.flow()['revision'], 'Scientist')
        self.store.edit([{'op':'edit_state','id':'plan','changes':{'x':500}}], self.store.flow()['revision'], 'Layout editor')
        story = read(self.store, 'plan')
        self.assertEqual(story['annotationAttribution']['recordedBy'], 'Scientist')
        self.assertEqual(story['state']['lastEditedBy'], 'Layout editor')

    def test_workflow_attempt_events_are_linked_to_the_correct_state(self):
        # Mimic stored adapter records to exercise the read model without an engine.
        def observed(flow):
            flow.setdefault('workflows', {'proposals':{}, 'runs':{}})['runs']['r'] = {
                'id':'r','proposalId':'p','stageNodes':{'stage':'plan'}}
            return {'run':{'id':'r','proposalId':'p'}}, None
        self.store.update('workflow.launch_reserved', 'Recorder', observed)
        self.store.update('workflow.finished', 'Recorder', lambda f:({'run':{'id':'r'}},None))
        self.assertIn('workflow.finished', [e['kind'] for e in read(self.store, 'plan')['timeline']])
        self.assertNotIn('workflow.finished', [e['kind'] for e in read(self.store, 'input')['timeline']])

    def test_removed_plan_archive_undo_and_id_reservation(self):
        self.add()
        flow = self.store.edit([{'op':'delete_state','id':'plan'}], self.store.flow()['revision'])
        self.assertEqual(archive_index(self.store)[0]['id'], 'plan')
        story = read(self.store, 'plan')
        self.assertEqual(story['archive']['label'], 'Removed plan')
        self.assertEqual(story['entries'][0]['summary'], self.decision['summary'])
        with self.assertRaises(RecordError):
            self.store.snapshot('Unrelated', [], ident='plan')
        self.store.undo(flow['revision'], flow['revision'])
        self.assertIsNone(read(self.store, 'plan')['archive'])

    def test_manual_archive_restores_recorded_states_and_relationships(self):
        from saigen.analysis_groups import replace
        from saigen.bookmarks import canvas_status, set_saved
        from saigen.views import CanvasView

        aid, done = self.store.begin('Completed result', ['input'], ['synthetic'], 'Runner', '', [], [], {}, {}, planned='plan')
        self.store.finish(aid, 'completed', 0, [], [])
        aid, failed = self.store.begin('Failed follow-up', [done], ['synthetic'], 'Runner', '', [], [], {}, {})
        before = self.store.finish(aid, 'failed', 1, [], [])
        replace(self.store, [{'id': 'results', 'title': 'Results', 'stateIds': [done, failed]}], before['revision'], 'Human')
        view = CanvasView(self.store)
        before = self.store.flow()
        set_saved(self.store, done, True)
        self.assertIn(done, view.flow()['archivableStateIds'])
        operation = {'op': 'archive_states', 'stateIds': [done, failed]}
        with self.assertRaises(RecordError):
            self.store.edit([{**operation, 'stateIds': [done, 'input_missing']}], before['revision'])
        self.assertNotIn('stateArchives', self.store.flow())
        archived = self.store.edit([operation], before['revision'])
        self.assertEqual(archived['revision'], before['revision'] + 1)
        for sid, status in [(done, 'completed'), (failed, 'failed')]:
            self.assertEqual(read(self.store, sid)['state']['status'], status)
            self.assertTrue(read(self.store, sid)['archive']['manual'])
            self.assertEqual(read(self.store, failed)['actions'][0]['from'], [done])
            with self.assertRaises(Conflict):
                set_archived(self.store, sid, False, archived['revision'] - 1, 'Human')
        reopened = Store(self.root)
        self.assertEqual({entry['status'] for entry in archive_index(reopened)}, {'completed', 'failed'})
        reopened.undo(archived['revision'], archived['revision'])
        self.assertNotIn('stateArchives', reopened.flow())
        hidden = reopened.edit([operation], reopened.flow()['revision'])
        set_archived(reopened, done, False, hidden['revision'], 'Human')
        self.assertEqual([entry['id'] for entry in archive_index(reopened)], [failed])
        set_archived(reopened, failed, False, reopened.flow()['revision'], 'Human')
        after = reopened.flow()
        for key in ('states', 'actions', 'artifacts', 'analysisGroups'):
            self.assertEqual(after[key], before[key])
        self.assertEqual(archive_index(reopened), [])
        self.assertEqual(canvas_status(reopened)['bookmarks'], [done])
        self.assertEqual([event['kind'] for event in read(reopened, done)['timeline'] if event['kind']=='flow.edited' and any(done in op.get('stateIds', []) for op in event['payload'].get('operations', []))],
                         ['flow.edited', 'flow.edited', 'flow.edited'])

    def test_manual_archive_keeps_active_plans_and_legacy_archives_separate(self):
        revision = self.store.flow()['revision']
        with self.assertRaises(RecordError):
            set_archived(self.store, 'plan', True, revision, 'Human')
        flow = self.store.edit([{'op': 'delete_state', 'id': 'plan'}], revision)
        self.assertEqual(archive_index(self.store), [{'id': 'plan', 'title': 'Initial plan', 'label': 'Removed plan'}])
        with self.assertRaises(RecordError):
            set_archived(self.store, 'plan', False, flow['revision'], 'Human')

    def test_replacement_cycle_is_rejected(self):
        self.add({'kind':'replacement','states':['input'],'summary':'Use proposed work','replacementStateId':'plan'})
        with self.assertRaises(RecordError):
            self.add({'kind':'replacement','states':['plan'],'summary':'Back to input','replacementStateId':'input'})

    def test_evidence_state_id_cannot_be_reused_after_removal(self):
        self.store.plan('Source plan', ['input'], 'Some evidence', ident='source_plan')
        self.add({**self.decision,'evidence':[{'type':'state','id':'source_plan','location':'Proposed expectation'}]})
        self.store.edit([{'op':'delete_state','id':'source_plan'}],self.store.flow()['revision'])
        with self.assertRaises(RecordError):
            self.store.snapshot('Unrelated result',[],ident='source_plan')

    def test_distinct_incoming_decisions_keep_their_action_scope(self):
        aid, sid=self.store.begin('Attempt',['input'],['synthetic'],'Runner','First purpose',[],[],{},{},planned='plan')
        self.add({**self.decision,'actions':[aid]})
        story=read(self.store,sid)
        self.assertEqual(story['entries'][0]['actions'],[aid])
        self.assertEqual(story['actions'][0]['reason'],'First purpose')
        self.assertEqual(story['entries'][0]['rationale'],self.decision['rationale'])

    def test_cancelled_workflow_retains_approval_and_decision(self):
        source = self.root/'source.tsv';source.write_text('a\tb\n1\t2\n')
        node = self.store.snapshot('Table', [source], ident='table')
        spec={'schemaVersion':1,'engine':{'name':'test','version':'1'},
              'pipeline':{'source':'synthetic','revision':'1','contentDigest':'test'},'configuration':{},
              'inputBindings':[{'name':'data','stateId':'table','artifactId':node['artifactIds'][0]}],
              'stages':[{'key':'step','title':'Expected result','dependsOn':[], 'expectedSummary':'A table',
                         'expectedFiles':[],'mapping':{'taskSelectors':['STEP']}}]}
        service = WorkflowService(self.store)
        proposal = service.propose(spec, revision=self.store.flow()['revision'], actor='Planner')
        sid = proposal['stageNodes']['step']
        service.approve(proposal['id'], proposal['executionDigest'], revision=self.store.flow()['revision'], actor='Approval recorder')
        self.add({**self.decision,'states':[sid]})
        service.cancel(proposal['id'], revision=self.store.flow()['revision'], reason='Different method requested')
        story = read(self.store, sid)
        self.assertEqual(story['archive']['reason'], 'Different method requested')
        self.assertTrue(any(p['name']=='Approval recorder' and p['role']=='Approval declared by' for p in story['participants']))
        self.assertTrue(any(e['kind']=='workflow.cancelled' for e in story['timeline']))
        self.assertEqual(story['entries'][0]['rationale'], self.decision['rationale'])

    def test_reconstruction_evidence_and_archived_story_remain_unobserved(self):
        from saigen.reconstruction import propose, review
        source=self.root/'chat.md';source.write_text('A previous result was reported.')
        spec={'id':'history','sources':{'chat':'chat.md'},'states':[{'id':'old','title':'Old result',
              'evidence':[{'source':'chat','location':'line 1','kind':'reported','note':'Execution unknown'}]}], 'connections':[]}
        propose(self.store, spec, self.store.flow()['revision'], 'Reconstructor')
        self.add({'kind':'interpretation','states':['old'],'summary':'A tentative historical explanation',
                  'evidenceKind':'inferred','evidence':[{'type':'artifact',
                   'id':self.store.flow()['reconstructions']['history']['sources']['chat'],'location':'line 1'}]})
        review(self.store, 'history', 'reject', self.store.flow()['revision'], 'Reviewer')
        story=read(self.store, 'old')
        self.assertEqual(story['archive']['label'], 'Rejected reconstruction')
        self.assertIsNone(story['state']['performedBy'])
        self.assertEqual(story['entries'][0]['evidenceKind'], 'inferred')

    def test_cli_writes_and_reads_explanations(self):
        path = self.root/'decision.json';path.write_text(json.dumps(self.decision))
        command = [sys.executable,'-B','-m','saigen']
        result = subprocess.run(command+['explain','--project',str(self.root),'--file',str(path),'--revision',str(self.store.flow()['revision'])],capture_output=True,text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        result = subprocess.run(command+['story','plan','--project',str(self.root)],capture_output=True,text=True,check=True)
        self.assertEqual(json.loads(result.stdout)['entries'][0]['summary'], self.decision['summary'])

    def test_http_auth_staleness_and_story_read(self):
        server=Server(('127.0.0.1',0),self.store)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        self.addCleanup(lambda:(server.shutdown(),server.server_close(),thread.join()))
        base=f'http://127.0.0.1:{server.server_port}'
        def request(token, revision):
            data=json.dumps({'entry':self.decision,'revision':revision}).encode()
            return urllib.request.urlopen(urllib.request.Request(base+'/api/explanations',data,
                {'Content-Type':'application/json','X-Saigen-Token':token}))
        revision=self.store.flow()['revision']
        with self.assertRaises(urllib.error.HTTPError) as error:request('wrong',revision)
        self.assertEqual(error.exception.code,403)
        with request(server.token,revision) as response:self.assertEqual(response.status,200)
        with self.assertRaises(urllib.error.HTTPError) as error:request(server.token,revision)
        self.assertEqual(error.exception.code,409)
        with urllib.request.urlopen(base+'/api/story/plan') as response:
            self.assertEqual(json.load(response)['entries'][0]['recordedBy'],'Human')
