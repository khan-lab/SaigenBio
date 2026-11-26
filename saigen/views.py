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
        flow['runOrder'] = self.run_order(flow)
        flow['actions'] = legacy_actions(flow)
        flow['removalOptions'] = removal_options(flow)
        archived = flow.get('stateArchives', {})
        flow['archivableStateIds'] = [
            state['id'] for state in flow['states']
            if can_archive(state) and state['id'] not in archived
        ]
        return flow

    def run_order(self, flow):
        actions = {action['id']: action for action in flow['actions']}
        workflows = flow.get('workflows', {}).get('runs', {})
        state_ids = {state['id'] for state in flow['states']}
        order = []
        number = 0
        for kind, payload in self.store.run_starts(flow['revision']):
            if kind == 'run.started':
                start = payload.get('action', {})
                if not start.get('startedAt'):
                    continue
                current = actions.get(start.get('id'), {})
                targets = [current.get('to')]
            else:
                start = payload.get('run', {})
                if not start.get('registeredAt'):
                    continue
                current = workflows.get(start.get('id'), {})
                targets = list(current.get('stageNodes', {}).values())
            number += 1
            targets = [target for target in targets if target in state_ids]
            if targets:
                order.append({'number': number, 'stateIds': targets})
        return order

    def history(self):
        events = self.store.events()
        for event in events:
            event.pop('inverse', None)
        return events
