"use strict";

globalThis.SaigenVerification=Object.freeze({create({escape:esc,shortDate,displayText,artifactName=id=>id}){
 const link=(id,label)=>'<button class="source-link" data-open="'+esc(id)+'">'+esc(label)+'</button>';
 function render(context){
  if(!context?.proposals?.length&&!context?.comparison)return '';
  let body='<p>Verification tests stated criteria under recorded conditions. It does not prove historical execution or scientific correctness.</p>';
  if(context.comparison){const c=context.comparison;body+='<h3>Comparison outcome · '+esc(c.status)+'</h3><p>'+link(c.originalStateId,'Original result')+' + '+link(c.candidateStateId,'Observed attempt')+'</p>'+c.criteria.map(r=>'<p><strong>'+esc(r.criterion.method)+' · '+esc(r.status)+'</strong> · '+esc(r.criterion.output)+'</p>'+(r.reason?'<p>'+esc(r.reason)+'</p>':'')+'<details><summary>Criteria and differences</summary><pre>'+esc(JSON.stringify(r,null,2))+'</pre></details>').join('');}
  for(const p of context.proposals||[]){
   const s=p.spec;body+='<article class="story-entry"><h3>'+esc(s.reason)+'</h3><p>'+link(s.originalStateId,'Original result')+'</p><details><summary>Review verification configuration</summary><h4>Why</h4><p>'+esc(s.reason)+'</p><h4>Prerequisites</h4><p>'+esc(s.prerequisites)+'</p><h4>Resources and cost expectations (declared)</h4><p>'+esc(s.resources)+'</p><h4>Command</h4><pre>'+esc(displayText(s.command.join(' ')))+'</pre><h4>Inputs, code, environment and criteria</h4><pre>'+esc(JSON.stringify({inputs:s.inputArtifactIds,code:s.codeArtifactIds,environment:s.environmentArtifactIds,outputs:s.outputs,criteria:s.criteria,runtime:s.runtime},null,2))+'</pre><p>Proposed by '+esc(p.writtenBy)+' · '+esc(shortDate(p.createdAt))+'</p></details>';
   body+='<p>Preserved code: '+(s.codeArtifactIds.length?s.codeArtifactIds.map(id=>'<button class="file-button" data-artifact="'+esc(id)+'">'+esc(artifactName(id))+'</button>').join(' · '):'No separate code file; inspect the recorded command.')+'</p>';
   body+=p.cancelled?'<p>Cancelled: '+esc(p.cancelled.reason)+'</p>':p.approval?'<p class="action-meta">Approval declared by '+esc(p.approval.declaredBy)+' · '+esc(shortDate(p.approval.at))+'. The agent executes through the CLI.</p>':'<button data-verify-approve="'+esc(p.id)+'" data-digest="'+esc(p.digest)+'">Record approval of this configuration</button>';
   const attempts=(context.attempts||[]).filter(a=>a.proposalId===p.id);
   body+=attempts.map(a=>'<p>'+(a.stateAvailable?link(a.stateId,'Attempt'):'Preparation (no observed attempt)')+' · '+esc(a.status)+(a.comparisonStateId?' · '+link(a.comparisonStateId,'Comparison: '+a.comparisonStatus):' · comparison not recorded')+'</p>').join('')+'</article>';
  }
  return '<section class="detail-section detail-card verification-panel"><h2>Verification</h2>'+body+'</section>';
 }
 return Object.freeze({render});
}});
