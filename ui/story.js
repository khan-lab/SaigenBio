"use strict";

// Renders the Engine's attributed story model; never derives scientific conclusions.
globalThis.SaigenStory=Object.freeze({create({escape:esc,shortDate,fileRows}){
 let actionLabels=new Map();
 const section=(label,body)=>'<section class="detail-section detail-card story-section" aria-label="'+label+'"><h2>'+label+'</h2>'+body+'</section>';
 const item=(label,body,level=3)=>body?'<h'+level+'>'+label+'</h'+level+'>'+body:'';
 const paragraph=value=>value?.trim()?'<p>'+esc(value)+'</p>':'';
 const stateLink=(id,title=id)=>'<button class="source-link" data-open="'+esc(id)+'">'+esc(title)+'</button>';
 function evidence(refs){return refs.length?'<details class="story-evidence"><summary>Supporting evidence · '+refs.length+'</summary><ul>'+refs.map(r=>'<li>'+(r.type==='artifact'?'<button class="file-button" data-artifact="'+esc(r.id)+'">Source file</button>':r.type==='state'?stateLink(r.id):'<a href="#event-'+esc(r.id)+'" data-event-link="'+esc(r.id)+'">Event '+esc(r.id)+'</a>')+' · '+esc(r.location)+'</li>').join('')+'</ul></details>':'';}
 function entry(e){
  let body='<article class="story-entry" id="explanation-'+esc(e.id)+'"><h3>'+esc(e.summary)+'</h3><p class="action-meta">'+esc(e.evidenceKind)+' statement · recorded by '+esc(e.recordedBy)+' · '+esc(shortDate(e.recordedAt))+'</p>';
  if(e.actions?.length)body+='<p class="action-meta">Applies to: '+e.actions.map(id=>esc(actionLabels.get(id)||id)).join(' · ')+'</p>';
  if(e.historicalAt)body+='<p>Reported historical date: '+esc(shortDate(e.historicalAt))+' <span class="detail-empty">(declared)</span></p>';
  if(e.kind==='decision'){
   body+=item('Rationale',paragraph(e.rationale),4);
   if(e.alternatives.length)body+=item('Alternatives considered','<ul>'+e.alternatives.map(a=>'<li>'+esc(a.option)+(a.reason?.trim()?' — '+esc(a.reason):'')+'</li>').join('')+'</ul>',4);
   body+=item('Basis for agreement',paragraph(e.agreementBasis),4);
  }
  body+=evidence(e.evidence)+'</article>';
  return e.supersededBy?'<details class="story-previous"><summary>Earlier statement (corrected)</summary>'+body+'<a href="#explanation-'+esc(e.supersededBy)+'" data-entry-link="'+esc(e.supersededBy)+'">View correction</a></details>':body;
 }
 function render(story,visual,artifacts,{navigation=false}={}){
  if(!story)return (visual?section('What',visual):'')+'<p class="detail-empty" role="status">Loading recorded information…</p>';
  const n=story.state,entries=story.entries||[],active=kind=>entries.filter(e=>e.kind===kind),actions=story.actions||[];
  actionLabels=new Map(actions.map(a=>[a.id,a.label||a.id]));
  const expectation=n.expectedSummary||story.originalPlan?.expectedSummary;
  let what=(story.archive?'<p class="story-badge">'+esc(story.archive.label)+'</p>'+paragraph(story.archive.reason):'')+item('Intended result',paragraph(expectation))+visual;
  const own=(n.artifactIds||[]).map(id=>artifacts[id]).filter(a=>a&&!['code','environment','log'].includes(a.role));
  if(own.length)what+=item(n.origin==='terminal'||n.reconstruction||n.status==='imported'?'Preserved files':'Recorded outputs','<ul class="files">'+fileRows(own)+'</ul>');
  for(const [kind,label] of [['question','Scientific question'],['finding','Recorded findings'],['interpretation','Interpretations'],['limitation','Limitations']]){
   what+=item(label,active(kind).map(entry).join(''));
  }
  if(n.note?.trim()){
   const attribution=story.annotationAttribution;
   const recorder=attribution?.recordedBy?'Recorded by '+esc(attribution.recordedBy):'';
   const date=attribution?.recordedAt?esc(shortDate(attribution.recordedAt)):'';
   what+='<details><summary>Current annotation</summary>'+paragraph(n.note)+'<p class="action-meta">Annotation; not automatically classified as a finding.'+
     (recorder||date?' '+[recorder,date].filter(Boolean).join(' · '):'')+'</p></details>';
  }
  const limitations=story.workflowProposal?.spec?.limitations||[];
  if(limitations.length)what+='<h3>Proposal limitations (declared)</h3><ul>'+limitations.map(l=>'<li>'+esc(l)+'</li>').join('')+'</ul>';
  if(story.originalPlan){
   const plan=story.originalPlan;
   const meta=[plan.writtenBy?'Proposed by '+esc(plan.writtenBy):'',plan.createdAt?esc(shortDate(plan.createdAt)):''].filter(Boolean).join(' · ');
   const body=paragraph(plan.title)+paragraph(plan.expectedSummary)+(meta?'<p class="action-meta">'+meta+'</p>':'');
   if(body)what+='<details><summary>Original recorded plan</summary>'+body+'</details>';
  }
  const decisions=active('decision');
  let why=decisions.map(entry).join('');
  for(const a of actions)if(a.reason?.trim())why+='<article class="story-entry"><h3>Stated purpose · '+esc(a.label||a.id)+'</h3>'+paragraph(a.reason)+'<p class="action-meta">'+(a.writtenBy?'Recorded by '+esc(a.writtenBy)+' · ':'')+esc(a.reasonSource||'Declared purpose')+'</p></article>';
  for(const e of story.replacements||[])why+='<article class="story-entry"><h3>Replacement relationship</h3><p>'+e.states.map(id=>stateLink(id)).join(' + ')+' → '+stateLink(e.replacementStateId)+'</p>'+entry(e)+'</article>';
  const who=story.participants.length?'<p class="detail-empty">Names and roles are declarations. Recorder identity does not establish approval.</p><ul class="story-people">'+story.participants.map(p=>{
   const context=p.explanationId?'<a href="#explanation-'+esc(p.explanationId)+'" data-entry-link="'+esc(p.explanationId)+'">'+esc(p.context)+'</a>':esc(p.context);
   const meta=[context,p.at?esc(shortDate(p.at)):''].filter(Boolean).join(' · ');
   return '<li><strong>'+esc(p.role)+'</strong> · '+esc(p.name)+(meta?'<small>'+meta+'</small>':'')+'</li>';
  }).join('')+'</ul>':'';
  const labels={'plan.proposed':'Plan proposed','run.started':'Execution started','run.finished':'Execution finished','run.completed':'Execution completed','run.failed':'Execution failed','run.cancelled':'Execution cancelled','run.contact_lost':'Recorder contact lost','workflow.launch_reserved':'Workflow launch reserved','workflow.run_observed':'Workflow run registered','workflow.finished':'Workflow attempt finished','workflow.evidence':'Workflow evidence recorded','workflow.reconciliation_failed':'Workflow reconciliation failed','workflow.contact_lost':'Workflow recorder contact lost','run.command':'Command recorded','flow.edited':'State or relationship edited','flow.undo':'Edit undone','workflow.proposed':'Workflow proposed','workflow.approved':'Workflow approval declared','workflow.cancelled':'Workflow cancelled','reconstruction.proposed':'Reconstruction recorded','reconstruction.reviewed':'Reconstruction reviewed','explanation.recorded':'Explanation or decision recorded'};
  const when=story.timeline.length?'<p class="detail-empty">Dates below are recorder event times. Reported historical dates remain attached to their statements.</p><ol class="story-timeline">'+story.timeline.map(e=>'<li id="event-'+esc(e.revision)+'"><details><summary>'+esc(labels[e.kind]||e.kind.replaceAll('.',' '))+'</summary><pre>'+esc(JSON.stringify(e.payload,null,2))+'</pre></details><p>'+esc(shortDate(e.at))+' · '+esc(e.actor)+' · Event '+esc(e.revision)+'</p></li>').join('')+'</ol>':'';
  const sections=[['What',what],['Why',why],['Who',who],['When',when]].filter(([,body])=>body);
  const jumps=navigation&&sections.length?'<nav class="story-jumps" aria-label="Result detail sections">'+sections.map(([label])=>'<button data-story-jump="'+label+'">'+label+'</button>').join('')+'</nav>':'';
  return jumps+sections.map(([label,body])=>section(label,body)).join('');
 }
 return Object.freeze({render});
}});
