"use strict";

globalThis.SaigenReconstruction=Object.freeze({create({getFlow,escape:esc,shortDate}){
 function render(n){
  const flow=getFlow(),proposals=flow.reconstructions||{},parts=[];
  const controls=(pid,kind,id)=>'<button data-reconstruction="'+esc(pid)+'" data-decision="accept"'+(kind?' data-'+kind+'-id="'+esc(id)+'"':'')+'>Accept '+(kind==='connection'?'relationship':kind==='evidence'?'evidence':kind==='state'?'state':'remaining items')+'</button> <button data-reconstruction="'+esc(pid)+'" data-decision="reject"'+(kind?' data-'+kind+'-id="'+esc(id)+'"':'')+'>Reject '+(kind||'remaining items')+'</button>';
  const evidence=items=>'<ul>'+items.map(e=>'<li><strong>'+esc(e.kind)+'</strong> · <button class="file-button" data-artifact="'+esc(e.artifactId)+'">'+esc(flow.artifacts[e.artifactId]?.name||e.source)+'</button> · '+esc(e.location)+'<p>'+esc(e.note)+'</p></li>').join('')+'</ul>';
  const incoming=[...new Map([...flow.actions,...Object.values(proposals).flatMap(p=>p.archivedActions||[])].filter(a=>a.to===n.id&&a.reconstruction).map(a=>[a.id,a])).values()];
  const own=n.reconstruction;
  if(own)parts.push('<h3>State evidence · '+esc(own.review)+'</h3>'+evidence(own.evidence||[])+(own.review==='draft'?controls(own.id,'state',n.id)+'<p class="detail-empty">Rejecting a draft state also archives its pending relationships.</p>':'')+(own.reviewedBy?'<p class="action-meta">Reviewed by '+esc(own.reviewedBy)+' · '+esc(shortDate(own.reviewedAt))+' · '+esc(own.reviewReason||'Reason not recorded')+'</p>':''));
  for(const action of incoming){const r=action.reconstruction;parts.push('<article class="story-entry"><h3>Relationship: '+esc(action.label)+' · '+esc(r.review)+'</h3>'+evidence(r.evidence||[])+(r.review==='draft'?controls(r.id,'connection',action.id):'<p class="action-meta">Reviewed by '+esc(r.reviewedBy||'Not recorded')+' · '+esc(shortDate(r.reviewedAt))+' · '+esc(r.reviewReason||'Reason not recorded')+'</p>')+'</article>');}
  const related=new Set([own?.id,...incoming.map(a=>a.reconstruction.id)].filter(Boolean));
  for(const p of Object.values(proposals))for(const update of p.evidenceUpdates||[]){
   if(update.targetId!==n.id&&!incoming.some(a=>a.id===update.targetId))continue;
   related.add(p.id);parts.push('<article class="story-entry"><h3>Additional evidence · '+esc(update.review)+'</h3>'+evidence(update.evidence)+(update.review==='draft'?controls(p.id,'evidence',update.id):'<p class="action-meta">Reviewed by '+esc(update.reviewedBy||'Not recorded')+' · '+esc(shortDate(update.reviewedAt))+' · '+esc(update.reviewReason||'Reason not recorded')+'</p>')+'</article>');
  }
  for(const id of related){const p=proposals[id];if(p&&['draft','partial'].includes(p.status))parts.push('<details><summary>Review remaining proposal items</summary><p>Inspect all remaining states, relationships and evidence before accepting. Accepted items are preserved.</p>'+controls(id,'',null)+'</details>');parts.push('<label class="field">Review reason (optional)<textarea data-review-reason="'+esc(id)+'" rows="2"></textarea></label>');}
  return parts.length?'<section class="detail-section detail-card"><h2>Reconstructed evidence</h2><p>Historical execution was not observed by SaigenBio. Acceptance records your review, not proof that the command ran.</p>'+parts.join('')+'</section>':'';
 }
 return Object.freeze({render});
}});
