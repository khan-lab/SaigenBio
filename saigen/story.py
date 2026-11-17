"""Attributed explanations and decision history, separate from execution facts."""
import copy
import json
from datetime import datetime

from .records import RecordError, now, text, uid

KINDS = {'question', 'finding', 'interpretation', 'limitation', 'decision', 'replacement'}
ROLES = {'proposer', 'contributor', 'approver', 'executor', 'recorder'}


def locate(flow, ident, events=()):
    if not isinstance(ident, str):
        raise RecordError('State ID must be text')
    for state in flow['states']:
        if state['id'] == ident:
            return state, None
    for proposal in flow.get('workflows', {}).get('proposals', {}).values():
        retirement = proposal.get('retirement', {})
        for state in retirement.get('states', []):
            if state['id'] == ident:
                return state, {'label': 'Cancelled proposal', **retirement, 'actions': retirement.get('actions', [])}
    for proposal in flow.get('reconstructions', {}).values():
        for state in proposal.get('archivedStates', []):
            if state['id'] == ident:
                return state, {'label': 'Rejected reconstruction', 'reason': 'Reconstruction rejected',
                               'actions': proposal.get('archivedActions', [])}
    for event in reversed(events):
        inverse = event.get('inverse') or []
        for operation in json.loads(inverse) if isinstance(inverse, str) else inverse:
            if operation.get('op') == 'restore_state' and operation.get('id') == ident:
                return operation['value'], {'label': 'Removed plan', 'reason': 'Plan removed',
                                            'actions': operation.get('related', [])}
    raise RecordError('Unknown state: ' + str(ident))


def archive_index(store):
    flow, events = store.flow(), store.events()
    events = [e for e in events if e['revision'] <= flow['revision']]
    ids = set()
    for proposal in flow.get('workflows', {}).get('proposals', {}).values():
        ids.update(n['id'] for n in proposal.get('retirement', {}).get('states', []))
    for proposal in flow.get('reconstructions', {}).values():
        ids.update(n['id'] for n in proposal.get('archivedStates', []))
    for event in events:
        inverse = event.get('inverse') or []
        ids.update(op['id'] for op in (json.loads(inverse) if isinstance(inverse, str) else inverse)
                   if op.get('op') == 'restore_state')
    result = []
    for ident in sorted(ids - {n['id'] for n in flow['states']}):
        state, archive = locate(flow, ident, events)
        result.append({'id': ident, 'title': state['title'], 'label': archive['label']})
    return result


def append(store, document, revision, actor='AI agent'):
    """Append a declaration or correction; never rewrite the referenced attempt."""
    required = {'kind', 'states', 'summary'}
    optional = {'actions', 'rationale', 'alternatives', 'agreementBasis', 'participants',
                'evidence', 'evidenceKind', 'historicalAt', 'supersedes', 'replacementStateId'}
    if not isinstance(document, dict) or not required <= document.keys() or document.keys() - required - optional:
        raise RecordError('Explanation needs kind, states, summary and supported optional fields')
    entry = copy.deepcopy(document)
    if not isinstance(entry['kind'], str) or entry['kind'] not in KINDS:
        raise RecordError('Unknown explanation kind')
    text(entry['summary'], 'summary', 20000, True)
    for key in ('states', 'actions'):
        value = entry.setdefault(key, [])
        if not isinstance(value, list) or len(value) > 50 or any(not isinstance(v, str) for v in value) or len(set(value)) != len(value):
            raise RecordError('Supply up to 50 unique ' + key)
    if not entry['states']:
        raise RecordError('An explanation needs at least one state')
    for key in ('rationale', 'agreementBasis'):
        text(entry.setdefault(key, ''), key)
    if entry['kind'] != 'decision' and any(entry.get(k) for k in ('rationale', 'agreementBasis', 'alternatives')):
        raise RecordError('Decision fields require kind decision')
    alternatives = entry.setdefault('alternatives', [])
    if not isinstance(alternatives, list) or len(alternatives) > 30:
        raise RecordError('Supply up to 30 alternatives')
    for alternative in alternatives:
        if not isinstance(alternative, dict) or set(alternative) != {'option', 'reason'}:
            raise RecordError('Alternative needs option and reason')
        text(alternative['option'], 'alternative', 4000, True)
        text(alternative['reason'], 'alternative reason', 4000)
    participants = entry.setdefault('participants', [])
    if not isinstance(participants, list) or len(participants) > 50:
        raise RecordError('Supply up to 50 participants')
    for participant in participants:
        if not isinstance(participant, dict) or set(participant) != {'name', 'role'} or not isinstance(participant['role'], str) or participant['role'] not in ROLES:
            raise RecordError('Participant needs a name and supported role')
        text(participant['name'], 'participant name', 200, True)
    classification = entry.setdefault('evidenceKind', 'reported')
    if not isinstance(classification, str) or classification not in {'direct', 'reported', 'inferred', 'unresolved'}:
        raise RecordError('Choose direct, reported, inferred or unresolved evidence')
    evidence = entry.setdefault('evidence', [])
    if not isinstance(evidence, list) or len(evidence) > 50:
        raise RecordError('Supply up to 50 evidence references')
    for reference in evidence:
        if not isinstance(reference, dict) or set(reference) != {'type', 'id', 'location'} or not isinstance(reference['type'], str) or reference['type'] not in {'artifact', 'state', 'event'}:
            raise RecordError('Evidence needs type (artifact/state/event), id and location')
        text(reference['location'], 'evidence location', 1000, True)
    if 'historicalAt' in entry:
        text(entry['historicalAt'], 'historical date', 100, True)
        try:
            if datetime.fromisoformat(entry['historicalAt'].replace('Z', '+00:00')).utcoffset() is None:
                raise ValueError()
        except ValueError as exc:
            raise RecordError('Historical date needs an ISO timestamp with timezone') from exc
    if entry['kind'] == 'replacement':
        text(entry.get('replacementStateId'), 'replacement state', 100, True)
    elif 'replacementStateId' in entry:
        raise RecordError('Replacement link requires kind replacement')
    events = store.events()
    entry.update(id=uid('ex'), recordedBy=actor, recordedAt=now(), source='declared')

    def change(flow):
        known = {e['revision'] for e in events}
        for sid in entry['states']:
            locate(flow, sid, events)
        for aid in entry['actions']:
            candidates = flow['actions'] + [a for sid in entry['states'] for a in (locate(flow, sid, events)[1] or {}).get('actions', [])]
            action = next((a for a in candidates if a['id'] == aid), None)
            if not action or action['to'] not in entry['states']:
                raise RecordError('Action must produce one of the referenced states')
        for ref in evidence:
            if ref['type'] == 'artifact':
                if not isinstance(ref['id'], str) or ref['id'] not in flow['artifacts']:
                    raise RecordError('Unknown evidence artifact')
            elif ref['type'] == 'state':
                locate(flow, ref['id'], events)
            elif type(ref['id']) is not int or ref['id'] not in known:
                raise RecordError('Unknown evidence event')
        entries = flow.setdefault('explanations', {})
        if 'supersedes' in entry:
            previous = entries.get(entry['supersedes']) if isinstance(entry['supersedes'], str) else None
            if not previous or previous['kind'] != entry['kind'] or set(previous['states']) != set(entry['states']):
                raise RecordError('Correction must refer to the same kind and states')
            if any(e.get('supersedes') == previous['id'] for e in entries.values()):
                raise RecordError('Correct the latest version of this explanation')
        if entry['kind'] == 'replacement':
            target = entry['replacementStateId']
            locate(flow, target, events)
            links = [(s, e['replacementStateId']) for e in entries.values() if e['kind'] == 'replacement' for s in e['states']]
            reachable = [target]; visited = set()
            while reachable:
                current = reachable.pop()
                if current in entry['states']:
                    raise RecordError('Replacement relationships cannot form a cycle')
                if current not in visited:
                    visited.add(current)
                    reachable.extend(b for a, b in links if a == current)
        entries[entry['id']] = entry
        return {'explanation': copy.deepcopy(entry)}, None

    return store.update('explanation.recorded', actor, change, revision)


def read(store, ident):
    """Build the four-section view from attributed records and explicit event links."""
    flow = store.flow()
    events = [e for e in store.events() if e['revision'] <= flow['revision']]
    state, archive = locate(flow, ident, events)
    actions = [a for a in flow['actions'] + (archive or {}).get('actions', []) if a['to'] == ident]
    entries = [e for e in flow.get('explanations', {}).values() if ident in e['states']]
    corrections = {e['supersedes']: e['id'] for e in entries if e.get('supersedes')}
    entries = [{**e, 'supersededBy': corrections.get(e['id'])} for e in entries]
    all_corrections = {e['supersedes']: e['id'] for e in flow.get('explanations', {}).values() if e.get('supersedes')}
    replacements = [{**e, 'supersededBy': all_corrections.get(e['id'])} for e in flow.get('explanations', {}).values()
                    if e['kind'] == 'replacement' and (ident in e['states'] or e['replacementStateId'] == ident)]
    aids = {a['id'] for a in actions}
    proposal_id = state.get('workflowProposal')
    reconstruction_id = state.get('reconstruction', {}).get('id')
    runs = flow.get('workflows', {}).get('runs', {})
    run_ids = {r['id'] for r in runs.values() if ident in r.get('stageNodes', {}).values()
               or r['id'] == state.get('workflowRun')
               or (not r.get('stageNodes') and r.get('proposalId') == proposal_id and proposal_id)}
    timeline = []
    original = state.get('plan')
    for event in events:
        payload = event['payload']
        relevant = (payload.get('state', {}).get('id') == ident or payload.get('action', {}).get('to') == ident
                    or any(op.get('id') in aids | {ident} for op in payload.get('operations', []))
                    or any(a in aids for a in payload.get('actions', []))
                    or ident in payload.get('explanation', {}).get('states', [])
                    or payload.get('run', {}).get('id') in run_ids
                    or payload.get('runId') in run_ids
                    or any(r in run_ids for r in payload.get('recovered', []))
                    or (proposal_id and (payload.get('proposalId') == proposal_id or payload.get('proposal', {}).get('id') == proposal_id))
                    or (reconstruction_id and payload.get('reconstruction', {}).get('id') == reconstruction_id))
        if relevant:
            timeline.append({'revision': event['revision'], 'at': event['at'], 'actor': event['actor'],
                             'kind': event['kind'], 'payload': payload})
            if event['kind'] == 'plan.proposed' and payload.get('state', {}).get('id') == ident:
                original = payload['state']  # Earliest recorded expectation, before later edits.
    participants = []
    def participant(name, role, context, at=None, explanation_id=None):
        if name:
            participants.append({'name': name, 'role': role, 'context': context, 'at': at,
                                 'identity': 'declared', 'explanationId': explanation_id})
    proposer = state if state['status'] == 'planned' else state.get('plan', {})
    participant(proposer.get('writtenBy') or (original or {}).get('writtenBy'), 'Proposer', 'Plan', proposer.get('createdAt'))
    participant(state.get('writtenBy'), 'Recorder', 'State record', state.get('createdAt'))
    for action in actions:
        participant(action.get('performedBy'), 'Execution actor', action.get('label') or 'Recorded attempt', action.get('startedAt'))
        participant(action.get('writtenBy'), 'Recorder', action.get('label') or 'Recorded attempt', action.get('startedAt') or action.get('createdAt'))
    proposal = flow.get('workflows', {}).get('proposals', {}).get(proposal_id, {})
    if proposal:
        stage = next((s for s in proposal['spec']['stages'] if s['key'] == state.get('workflowStage')), None)
        if stage:
            original = {**stage, 'writtenBy': proposal.get('writtenBy'), 'createdAt': proposal.get('createdAt')}
        participant(proposal.get('writtenBy'), 'Proposer', 'Workflow proposal', proposal.get('createdAt'))
        approval = proposal.get('approval') or {}
        participant(approval.get('declaredBy'), 'Approval declared by', 'Workflow configuration', approval.get('at'))
    reconstruction = state.get('reconstruction', {})
    participant(reconstruction.get('reviewedBy'), 'Reconstruction reviewer', 'Review, not historical execution approval', reconstruction.get('reviewedAt'))
    for entry in entries:
        context = ('Earlier statement: ' if entry.get('supersededBy') else '') + entry['summary']
        participant(entry['recordedBy'], 'Recorder', context, entry['recordedAt'], entry['id'])
        for person in entry['participants']:
            participant(person['name'], person['role'].capitalize(), context, entry.get('historicalAt'), entry['id'])
    annotation = {'recordedBy': state.get('writtenBy'), 'recordedAt': state.get('createdAt')}
    for event in timeline:
        if event['payload'].get('state', {}).get('id') == ident and event['kind'] in {'run.started', 'snapshot.imported'}:
            annotation = {'recordedBy': event['actor'], 'recordedAt': event['at']}
        for operation in event['payload'].get('operations', []):
            if operation.get('id') == ident and 'note' in operation.get('changes', {}):
                annotation = {'recordedBy': event['actor'], 'recordedAt': event['at']}
    return {'revision': flow['revision'], 'state': state, 'archive': archive, 'actions': actions,
            'originalPlan': original, 'entries': entries, 'participants': participants,
            'timeline': timeline, 'replacements': replacements, 'workflowProposal': proposal or None,
            'annotationAttribution': annotation}
