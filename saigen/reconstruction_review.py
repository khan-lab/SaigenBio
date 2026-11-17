"""Item-level review and additive evidence acceptance; historical facts stay unobserved."""
import copy

from .records import RecordError, now, text


def review(store, ident, decision, revision, actor, *, state_id=None, connection_id=None, evidence_id=None, reason=''):
    if decision not in {'accept','reject'}:
        raise RecordError('Choose accept or reject')
    if sum(v is not None for v in (state_id,connection_id,evidence_id)) > 1:
        raise RecordError('Select one review item, or omit selectors for remaining items')
    text(reason,'review reason')

    def change(flow):
        proposal=flow.get('reconstructions',{}).get(ident)
        if not proposal:
            raise RecordError('Unknown reconstruction')
        nodes=[n for n in flow['states'] if n['id'] in proposal['states']]
        actions=[a for a in flow['actions'] if a['id'] in proposal['actions']]
        updates=proposal.get('evidenceUpdates',[])
        whole=state_id is None and connection_id is None and evidence_id is None
        selected_nodes=nodes if whole else [n for n in nodes if n['id']==state_id]
        selected_actions=actions if whole else [a for a in actions if a['id']==connection_id]
        selected_updates=updates if whole else [u for u in updates if u['id']==evidence_id]
        pending=lambda item:item.get('reconstruction',item).get('review')=='draft'
        selected_nodes=[n for n in selected_nodes if pending(n)]
        selected_actions=[a for a in selected_actions if pending(a)]
        selected_updates=[u for u in selected_updates if pending(u)]
        if not selected_nodes and not selected_actions and not selected_updates:
            raise RecordError('No pending selected review items')
        rejected_ids={n['id'] for n in selected_nodes} if decision=='reject' else set()
        if rejected_ids:
            if any(rejected_ids.intersection(p['spec'].get('contextStateIds',[])) for p in flow.get('workflows',{}).get('proposals',{}).values()):
                raise RecordError('A workflow references this reconstruction')
            own=set(proposal['actions'])
            if any(a['id'] not in own and (a['to'] in rejected_ids or rejected_ids.intersection(a['from'])) for a in flow['actions']) or any(n['id'] not in rejected_ids and rejected_ids.intersection(n.get('planParents',[])) for n in flow['states']):
                raise RecordError('Other work depends on this reconstruction')
            selected_actions=list({a['id']:a for a in selected_actions+[a for a in actions if pending(a) and (a['to'] in rejected_ids or rejected_ids.intersection(a['from']))]}.values())
        def mark(item):
            target=item.get('reconstruction',item)
            target.update(review='accepted' if decision=='accept' else 'rejected',reviewedBy=actor,reviewedAt=now(),reviewReason=reason)
        for node in selected_nodes:
            mark(node)
            if decision=='accept':node['origin']='reconstructed'
        accepted={n['id'] for n in flow['states'] if n.get('reconstruction',{}).get('review','accepted')=='accepted'}
        for action in selected_actions:
            if decision=='accept' and any(s not in accepted for s in action['from']+[action['to']]):
                raise RecordError('Accept relationship endpoints first, or reject the unsupported relationship')
            mark(action)
        for update in selected_updates:
            group='states' if update['targetType']=='state' else 'actions'
            target=next((v for v in flow[group] if v['id']==update['targetId']),None)
            if not target or target.get('reconstruction',{}).get('review','accepted')!='accepted':
                raise RecordError('Evidence target is no longer present and accepted')
            mark(update)
            if decision=='accept':target.setdefault('evidenceUpdates',[]).append(copy.deepcopy(update))
        if decision=='reject':
            node_ids={n['id'] for n in selected_nodes};action_ids={a['id'] for a in selected_actions}
            proposal.setdefault('archivedStates',[]).extend(copy.deepcopy(selected_nodes))
            proposal.setdefault('archivedActions',[]).extend(copy.deepcopy(selected_actions))
            flow['states']=[n for n in flow['states'] if n['id'] not in node_ids]
            flow['actions']=[a for a in flow['actions'] if a['id'] not in action_ids]
        items=[n['reconstruction'] for n in nodes]+[a['reconstruction'] for a in actions]+updates
        items += [v['reconstruction'] for v in proposal.get('archivedStates',[])+proposal.get('archivedActions',[]) if v['id'] not in {n['id'] for n in nodes+actions}]
        reviews={v['review'] for v in items}
        proposal['status']='draft' if reviews=={'draft'} else 'partial' if 'draft' in reviews else 'accepted' if reviews=={'accepted'} else 'rejected' if reviews=={'rejected'} else 'reviewed'
        proposal.update(reviewedBy=actor,reviewedAt=now())
        return {'reconstruction':copy.deepcopy(proposal),'selection':{'stateId':state_id,'connectionId':connection_id,'evidenceId':evidence_id},'decision':decision,'reason':reason},None

    return store.update('reconstruction.reviewed',actor,change,revision)
