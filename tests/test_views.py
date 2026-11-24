"""Canvas responses may enrich presentation without rewriting analysis records."""
import tempfile
import unittest
from pathlib import Path

from saigen.bookmarks import canvas_status, set_saved
from saigen.records import RecordError
from saigen.store import Store
from saigen.views import CanvasView


class CanvasViewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = Store(self.root)
        self.store.init('View test')
        source = self.root / 'counts.csv'
        source.write_text('sample,count\na,2\n')
        self.store.snapshot('Counts', [source], ident='counts')
        # Older projects did not capture table previews at import time.
        def legacy(flow):
            for artifact in flow['artifacts'].values():
                artifact.pop('tablePreview', None)
            return {}, None
        self.store.update('test.legacy', 'Test', legacy)
        self.view = CanvasView(self.store)

    def test_legacy_previews_and_removal_options_do_not_change_records(self):
        before = self.store.flow()
        events = self.store.events()
        flow = self.view.flow()
        artifact = next(iter(flow['artifacts'].values()))
        self.assertEqual(artifact['tablePreview']['rows'], [['a', '2']])
        self.assertIn('removalOptions', flow)
        self.assertEqual(self.view.flow(), flow)
        self.assertEqual(self.store.flow(), before)
        self.assertEqual(self.store.events(), events)
        # A view's derived capabilities cannot authorize deletion.
        with self.assertRaises(RecordError):
            self.store.edit([{'op':'delete_state', 'id':'counts'}], before['revision'])
        self.assertEqual(self.store.flow(), before)

    def test_missing_preserved_file_does_not_break_graph_response(self):
        artifact = next(iter(self.store.flow()['artifacts'].values()))
        self.store.artifact_path(artifact).unlink()
        flow = self.view.flow()
        self.assertEqual(flow['states'][0]['id'], 'counts')
        self.assertNotIn('tablePreview', flow['artifacts'][artifact['id']])

    def test_history_hides_inverse_but_keeps_undo_capability(self):
        before = self.store.flow()
        self.store.edit([{'op':'edit_state','id':'counts','changes':{'note':'Reviewed'}}], before['revision'])
        stored = self.store.events()
        history = self.view.history()
        self.assertTrue(history[-1]['undoable'])
        self.assertNotIn('inverse', history[-1])
        self.assertEqual(self.store.events(), stored)
        self.store.undo(history[-1]['revision'], self.store.flow()['revision'])
        self.assertEqual(self.store.flow()['states'][0]['note'], '')

    def test_bookmarks_persist_separately_from_graph_and_history(self):
        before = self.store.flow()
        events = self.store.events()
        self.assertEqual(canvas_status(self.store), {'revision': before['revision'], 'bookmarks': []})
        self.assertEqual(set_saved(self.store, 'counts', True), ['counts'])
        self.assertEqual(set_saved(self.store, 'counts', True), ['counts'])
        self.assertEqual(canvas_status(Store(self.root))['bookmarks'], ['counts'])
        with self.assertRaises(RecordError):
            set_saved(self.store, 'missing', True)
        with self.assertRaises(RecordError):
            set_saved(self.store, 'counts', 1)
        self.assertEqual(self.store.flow(), before)
        self.assertEqual(self.store.events(), events)
        self.assertEqual(set_saved(self.store, 'counts', False), [])

    def test_removing_a_state_clears_its_bookmark(self):
        self.store.plan('Proposed result', ['counts'], 'Expected output', ident='plan')
        set_saved(self.store, 'plan', True)
        self.store.edit([{'op': 'delete_state', 'id': 'plan'}], self.store.flow()['revision'])
        self.assertEqual(canvas_status(self.store)['bookmarks'], [])
