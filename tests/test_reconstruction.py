import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from saigen.store import Store, RecordError, Conflict
from saigen.reconstruction import propose, review, setup_context, show
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

    def renamed_spec(self):
        spec = copy.deepcopy(self.spec)
        spec['id'] = 'r2'
        spec['states'][0]['id'] = 'renamed'
        return spec

    def test_duplicate_evidence_cannot_be_reimported_with_fresh_ids_or_paths(self):
        flow = self.publish()
        spec = self.renamed_spec()
        (self.root/'copy.md').write_bytes((self.root/'chat.md').read_bytes())
        (self.root/'copy.csv').write_bytes((self.root/'result.csv').read_bytes())
        spec['sources'] = {'renamed_source': 'copy.md'}
        spec['states'][0].update(title='Renamed result', files=['copy.csv'])
        spec['states'][0]['evidence'][0]['source'] = 'renamed_source'
        with self.assertRaisesRegex(RecordError, 'already imported'):
            propose(self.store, spec, flow['revision'], 'Agent')
        self.assertEqual(self.store.flow(), flow)
        # Result contents participate in identity, not just the source note.
        (self.root/'copy.csv').write_text('a,b\n3,4\n')
        flow = propose(self.store, spec, flow['revision'], 'Agent')
        self.assertEqual(len(flow['states']), 2)

    def test_graph_identity_survives_reordering_and_endpoint_renaming(self):
        self.spec['states'].append({'id':'second','title':'Second result','evidence':[
            {**self.evidence, 'location':'line 2'}]})
        self.spec['connections'] = [{'from':['old'], 'to':'second', 'evidence':[self.evidence]}]
        flow = self.publish()
        spec = self.renamed_spec()
        spec['states'][1]['id'] = 'new_second'
        spec['states'].reverse()
        spec['connections'][0].update({'from':['renamed'], 'to':'new_second'})
        with self.assertRaisesRegex(RecordError, 'already imported'):
            propose(self.store, spec, flow['revision'], 'Agent')

    def test_revision_and_alternative_require_explicit_link_and_reason(self):
        flow = self.publish()
        spec = self.renamed_spec()
        spec['relation'] = {'proposal':'r1', 'kind':'revision', 'reason':'Correct the evidence classification'}
        with self.assertRaisesRegex(RecordError, 'Reject the earlier draft'):
            propose(self.store, spec, flow['revision'], 'Agent')
        flow = review(self.store, 'r1', 'reject', flow['revision'], 'Human')
        flow = propose(self.store, spec, flow['revision'], 'Agent')
        self.assertEqual(flow['reconstructions']['r2']['spec']['relation'], spec['relation'])
        alternative = copy.deepcopy(spec)
        alternative['id'] = 'r3'
        alternative['states'][0]['id'] = 'alternative'
        alternative['relation'] = {'proposal':'r2', 'kind':'alternative', 'reason':'Another interpretation'}
        flow = propose(self.store, alternative, flow['revision'], 'Agent')
        self.assertEqual(len(flow['states']), 2)

    def test_invalid_relations_do_not_change_project(self):
        flow = self.publish()
        for relation in (None, {}, {'proposal':'missing', 'kind':'alternative', 'reason':'Explain'},
                         {'proposal':'r1', 'kind':'alternative', 'reason':''}):
            spec = self.renamed_spec()
            spec['relation'] = relation
            with self.subTest(relation=relation), self.assertRaises(RecordError):
                propose(self.store, spec, flow['revision'], 'Agent')
            self.assertEqual(self.store.flow(), flow)

    def test_legacy_proposals_still_prevent_duplicate_evidence(self):
        flow = self.publish()
        def legacy(flow):
            proposal = flow['reconstructions']['r1']
            proposal.pop('evidenceFingerprint')
            proposal['fingerprint'] = 'old-id-dependent-hash'
            return {}, None
        flow = self.store.update('test.legacy', 'Test', legacy, flow['revision'])
        with self.assertRaisesRegex(RecordError, 'already imported'):
            propose(self.store, self.renamed_spec(), flow['revision'], 'Agent')

    def test_show_cli_includes_edits_original_spec_and_review_metadata(self):
        flow = self.publish()
        flow = self.store.edit([{'op':'edit_state', 'id':'old',
                                'changes':{'title':'User corrected title', 'note':'User clarification'}}],
                               flow['revision'], 'Human')
        result = subprocess.run([sys.executable, '-B', '-m', 'saigen', 'reconstruct', 'show',
                                 '--project', str(self.root), '--id', 'r1'],
                                check=True, capture_output=True, text=True)
        proposal = json.loads(result.stdout)['r1']
        self.assertEqual(proposal['graph']['source'], 'current')
        self.assertEqual(proposal['graph']['states'][0]['title'], 'User corrected title')
        self.assertEqual(proposal['graph']['states'][0]['note'], 'User clarification')
        self.assertEqual(proposal['spec'], self.spec)
        self.assertEqual(proposal['projectRevision'], flow['revision'])
        flow = review(self.store, 'r1', 'accept', flow['revision'], 'Reviewer')
        proposal = show(self.store, 'r1')['r1']
        self.assertEqual(proposal['reviewedBy'], 'Reviewer')
        self.assertEqual(proposal['graph']['states'][0]['reconstruction']['review'], 'accepted')
        self.assertEqual(proposal['spec'], self.spec)
        with self.assertRaisesRegex(RecordError, 'Unknown reconstruction'):
            show(self.store, 'missing')

    def test_show_rejected_proposal_uses_archive_with_final_edits(self):
        flow = self.publish()
        flow = self.store.edit([{'op':'edit_state', 'id':'old', 'changes':{'note':'Incorrect source'}}],
                               flow['revision'], 'Human')
        review(self.store, 'r1', 'reject', flow['revision'], 'Reviewer')
        proposal = show(self.store)['r1']
        self.assertEqual(proposal['graph']['source'], 'archive')
        self.assertEqual(proposal['graph']['states'][0]['note'], 'Incorrect source')
        self.assertEqual(proposal['status'], 'rejected')
        self.assertFalse(proposal['missingStateIds'])

    def test_in_place_setup_preserves_instructions_and_refreshes_managed_block(self):
        import contextlib, io
        from saigen.onboarding import initialize
        from saigen.workspace import setup, BLOCK_START
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = b'# Project rules\r\nKeep these instructions.\r\n'
            (root/'AGENTS.md').write_bytes(original)
            with contextlib.redirect_stdout(io.StringIO()):
                initialize(Store(root), name='Existing', agents=['codex'], non_interactive=True,
                           existing_project='.', start_viewer=False)
            instructions = root/'AGENTS.md'
            self.assertTrue(instructions.read_bytes().startswith(original))
            with instructions.open('a') as handle:
                handle.write('\nAdditional user rules.\n')
            setup(root, ['opencode'], '.', [])
            content = instructions.read_bytes()
            self.assertTrue(content.startswith(original))
            self.assertTrue(content.endswith(b'Additional user rules.\n'))
            self.assertIn(b'.opencode/skills/saigen-record', content)
            self.assertEqual(content.count(BLOCK_START.encode()), 1)
            setup(root, ['opencode'], '.', [])
            self.assertEqual(instructions.read_bytes(), content)
            # Recreating a removed instruction file still yields one managed block.
            instructions.unlink()
            setup(root, ['opencode'], '.', [])
            restored = instructions.read_bytes()
            setup(root, ['opencode'], '.', [])
            self.assertEqual(instructions.read_bytes(), restored)
            self.assertEqual(restored.count(BLOCK_START.encode()), 1)

    def test_in_place_setup_never_overwrites_custom_skill_or_edited_managed_block(self):
        from saigen.workspace import prepare, write_files, setup
        workspace = self.root/'protected'
        workspace.mkdir()
        (workspace/'AGENTS.md').write_text('User rules')
        custom = workspace/'.agents/skills/saigen-record/SKILL.md'
        custom.parent.mkdir(parents=True)
        custom.write_text('Custom skill')
        with self.assertRaises(RecordError):
            prepare(workspace, ['codex'], '.', [], preserve_instructions=True)
        self.assertEqual((workspace/'AGENTS.md').read_text(), 'User rules')
        self.assertEqual(custom.read_text(), 'Custom skill')
        custom.unlink()
        root, files, _ = prepare(workspace, ['codex'], '.', [], preserve_instructions=True)
        write_files(root, files)
        instructions = workspace/'AGENTS.md'
        instructions.write_text(instructions.read_text().replace('For analysis requests', 'My changed policy'))
        before = instructions.read_bytes()
        with self.assertRaisesRegex(RecordError, 'block was edited'):
            setup(workspace, ['opencode'], '.', [])
        self.assertEqual(instructions.read_bytes(), before)
