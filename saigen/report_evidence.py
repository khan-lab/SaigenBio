"""Select attributed narrative/verification context for frozen report exports."""
import json


def collect(flow, selection, events):
    selected=set(selection)
    actions={a['id'] for a in flow['actions'] if a['to'] in selected}
    entries=[e for e in flow.get('explanations',{}).values() if selected.intersection(e['states'])]
    verification=flow.get('verifications',{})
    attempts=[a for a in verification.get('attempts',{}).values() if selected.intersection({a['stateId'],a.get('comparisonStateId')})]
    pids={a['proposalId'] for a in attempts}
    proposals=[p for p in verification.get('proposals',{}).values() if p['id'] in pids or p['spec']['originalStateId'] in selected]
    pids.update(p['id'] for p in proposals)
    attempts=[a for a in verification.get('attempts',{}).values() if a['proposalId'] in pids]
    updates=[{**u,'targetStateIds':[u['targetId']] if u['targetType']=='state' else [a['to'] for a in flow['actions'] if a['id']==u['targetId']]}
             for p in flow.get('reconstructions',{}).values() for u in p.get('evidenceUpdates',[])
             if u['targetId'] in selected|actions]
    artifact_ids={r['id'] for e in entries for r in e['evidence'] if r['type']=='artifact'}
    artifact_ids.update(e['artifactId'] for u in updates for e in u['evidence'])
    reconstruction_reviews=[]
    for p in flow.get('reconstructions',{}).values():
        rejected=[a for a in p.get('archivedActions',[]) if a['to'] in selected]
        if selected.intersection(p['states']) or rejected or any(u['proposalId']==p['id'] for u in updates):
            reconstruction_reviews.append({k:p.get(k) for k in ('id','status','reviewedBy','reviewedAt')}|{'rejectedRelationships':rejected})
            artifact_ids.update(e['artifactId'] for a in rejected for e in a['reconstruction']['evidence'])
    for p in proposals:artifact_ids.update(p['spec']['artifactHashes'])
    related_states={a['stateId'] for a in attempts}
    comparison_ids={a['comparisonStateId'] for a in attempts if a.get('comparisonStateId')}
    attempt_states=[n for n in flow['states'] if n['id'] in related_states]
    attempt_actions=[a for a in flow['actions'] if a['to'] in related_states]
    comparisons=[n['verificationComparison'] for n in flow['states'] if n['id'] in comparison_ids]
    for n in attempt_states:artifact_ids.update(n.get('artifactIds',[]))
    for a in attempt_actions:
        artifact_ids.update(a.get('logs',[])+a.get('inputArtifacts',[])+a.get('code',{}).get('scriptArtifacts',[])+a.get('environment',{}).get('capturedFiles',[]))
    for n in flow['states']:
        if n['id'] in selected:
            artifact_ids.update(e['artifactId'] for e in n.get('reconstruction',{}).get('evidence',[]))
            for r in n.get('verificationComparison',{}).get('criteria',[]):
                artifact_ids.update(v for v in (r['originalArtifactId'],r.get('candidateArtifactId')) if v)
    for a in flow['actions']:
        if a['id'] in actions:artifact_ids.update(e['artifactId'] for e in a.get('reconstruction',{}).get('evidence',[]))
    event_ids={r['id'] for e in entries for r in e['evidence'] if r['type']=='event'}
    return {'explanations':entries,'evidenceUpdates':updates,'reconstructionReviews':reconstruction_reviews,'verifications':{'proposals':proposals,'attempts':attempts,'comparisons':comparisons,'attemptStates':attempt_states,'attemptActions':attempt_actions},
            'evidenceEvents':[{k:v for k,v in e.items() if k!='inverse'} for e in events if e['revision'] in event_ids and e['revision']<=flow['revision']]},artifact_ids


def describe(state, node, context, txt, code_cell):
    body=state['overview'];history=state['environment']
    entries=[e for e in context['explanations'] if node['id'] in e['states']]
    superseded={e['supersedes'] for e in entries if e.get('supersedes')}
    if entries:body+=['### Recorded explanations and decisions','']
    for e in entries:
        body += [txt(e['kind'].capitalize()+(' · earlier version (corrected)' if e['id'] in superseded else ''))+': '+txt(e['summary']),'',
                 'Evidence: '+txt(e['evidenceKind'])+' · recorded by '+txt(e['recordedBy'])+' · '+txt(e['recordedAt']),'']
        if e.get('historicalAt'):body+=['Reported historical date (declared): '+txt(e['historicalAt']),'']
        if e['kind']=='decision':
            body+=['Rationale: '+txt(e['rationale'] or 'Not recorded'),'','Basis for agreement: '+txt(e['agreementBasis'] or 'Not recorded'),'']
            body+=['Alternative: '+txt(a['option'])+' · '+txt(a['reason'] or 'Reason not recorded') for a in e['alternatives']]+['']
        for person in e['participants']:body+=['Declared '+txt(person['role'])+': '+txt(person['name']),'']
        for ref in e['evidence']:body+=['Supporting '+txt(ref['type'])+' '+txt(str(ref['id']))+' · '+txt(ref['location']),'']
        history+=code_cell(json.dumps(e,indent=2),'json')
    relevant=[u for u in context['evidenceUpdates'] if node['id'] in u['targetStateIds']]
    for u in relevant:
        body+=['Additional reconstruction evidence · '+txt(u['review']),'']
        for e in u['evidence']:body += [txt(e['kind'])+': '+txt(e['note'])+' · '+txt(e['source'])+' · '+txt(e['location']),'']
    for p in context['reconstructionReviews']:
        for action in p['rejectedRelationships']:
            if action['to']!=node['id']:continue
            review=action['reconstruction']
            body+=['Rejected historical relationship: '+txt(action['label'])+' · '+txt(review.get('reviewReason') or 'Reason not recorded'),'']
            for e in review['evidence']:body+=[txt(e['kind'])+': '+txt(e['note'])+' · '+txt(e['location']),'']
    if node.get('verificationComparison'):
        comparison=node['verificationComparison']
        body+=['### Verification comparison','',txt(comparison['status'])+' · '+txt(comparison['meaning']),'']
        for r in comparison['criteria']:
            body+=[txt(r['criterion']['method'])+' · '+txt(r['status'])+' · '+txt(r['criterion']['output']),'']
            if r.get('reason'):body+=[txt(r['reason']),'']
        history+=code_cell(json.dumps(comparison,indent=2),'json')
    for p in context['verifications']['proposals']:
        if p['spec']['originalStateId']==node['id']:
            body+=['Verification proposal: '+txt(p['spec']['reason']),'','Approval is a declaration, not proof of historical execution.','']
            for attempt in context['verifications']['attempts']:
                if attempt['proposalId']==p['id']:body+=['Observed attempt '+txt(attempt['stateId'])+': '+txt(attempt['status'])+' · comparison: '+txt(attempt.get('comparisonStatus','Not recorded')),'']
            history+=code_cell(json.dumps(p,indent=2),'json')
