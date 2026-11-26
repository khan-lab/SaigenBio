"""Derived Canvas responses from Engine records; never persist display metadata."""
from pathlib import Path

from .records import RecordError
from .lineage import legacy_actions
from .store import table_preview
from .state_archive import can_archive
from .workflows.service import removal_options


class CanvasView:
    """Build transport-independent graph/history responses for a local viewer."""

    def __init__(self, store):
        self.store = store
        self.preview_cache = {}

    def flow(self):
        flow = self.store.flow()
        for artifact in flow['artifacts'].values():
            suffix = Path(artifact['name']).suffix.lower()
            if artifact.get('tablePreview') or artifact.get('storage') != 'preserved' or suffix not in {'.csv', '.tsv'}:
                continue
            key = (artifact['sha256'], suffix)
            if key not in self.preview_cache:
                try:
                    self.preview_cache[key] = table_preview(self.store.artifact_path(artifact), artifact['name'])
                except (RecordError, OSError):
                    continue
            artifact['tablePreview'] = self.preview_cache[key]
        return self.decorate(flow)

    def decorate(self, flow):
        # Operates on the caller's detached response, never on stored records.
        flow['actions'] = legacy_actions(flow)
        flow['removalOptions'] = removal_options(flow)
        archived = flow.get('stateArchives', {})
        flow['archivableStateIds'] = [
            state['id'] for state in flow['states']
            if can_archive(state) and state['id'] not in archived
        ]
        return flow

    def history(self):
        events = self.store.events()
        for event in events:
            event.pop('inverse', None)
        return events
