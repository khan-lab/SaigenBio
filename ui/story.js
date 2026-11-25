"use strict";

// Renders the Engine's attributed story model; never derives scientific conclusions.
globalThis.SaigenStory=Object.freeze({create({escape:esc,shortDate}){
 let actionLabels=new Map();
 const section=(label,body)=>'<section class="detail-section detail-card story-section" aria-label="'+label+'"><h2>'+label+'</h2>'+body+'</section>';
 const item=(label,body,level=3)=>body?'<h'+level+'>'+label+'</h'+level+'>'+body:'';
 const paragraph=value=>value?.trim()?'<p>'+esc(value)+'</p>':'';
 const stateLink=(id,title=id)=>'<button class="source-link" data-open="'+esc(id)+'">'+esc(title)+'</button>';
 function evidence(refs){return refs.length?'<ul>'+refs.map(r=>'<li>'+(r.type==='artifact'?'<button class="file-button" data-artifact="'+esc(r.id)+'">Source file</button>':r.type==='state'?stateLink(r.id):'<a href="#event-'+esc(r.id)+'" data-event-link="'+esc(r.id)+'">Event '+esc(r.id)+'</a>')+' · '+esc(r.location)+'</li>').join('')+'</ul>':'';}
 function entry(e){
  const evidenceCue=e.kind==='finding'&&e.evidenceKind!=='direct'
   ? '<span class="story-badge">'+esc({reported:'Reported finding',inferred:'Inferred finding',unresolved:'Unresolved finding'}[e.evidenceKind]||'')+'</span>' : '';
  let body='<article class="story-entry" id="explanation-'+esc(e.id)+'">'+evidenceCue+'<p class="story-summary">'+esc(e.summary)+'</p>';
  const attribution=[e.evidenceKind?e.evidenceKind+' statement':'',e.recordedBy?'recorded by '+e.recordedBy:'',e.recordedAt?shortDate(e.recordedAt):''].filter(Boolean).join(' · ');
  let supporting=attribution?'<p class="action-meta">'+esc(attribution)+'</p>':'';
  if(e.actions?.length)supporting+='<p class="action-meta">Applies to '+e.actions.map(id=>esc(actionLabels.get(id)||id)).join(' · ')+'</p>';
  if(e.historicalAt)supporting+='<p>Reported historical date · '+esc(shortDate(e.historicalAt))+'</p>';
  if(e.kind==='decision'){
   body+=item('Rationale',paragraph(e.rationale),4);
   if(e.alternatives.length)body+=item('Alternatives considered','<ul>'+e.alternatives.map(a=>'<li>'+esc(a.option)+(a.reason?.trim()?' — '+esc(a.reason):'')+'</li>').join('')+'</ul>',4);
   body+=item('Basis for agreement',paragraph(e.agreementBasis),4);
  }
  supporting+=evidence(e.evidence||[]);
  if(supporting)body+='<details class="story-evidence"><summary>'+(e.evidence?.length?'Attribution &amp; evidence · '+e.evidence.length:'Attribution')+'</summary>'+supporting+'</details>';
  body+='</article>';
  return e.supersededBy?'<details class="story-previous"><summary>Earlier statement (corrected)</summary>'+body+'<a href="#explanation-'+esc(e.supersededBy)+'" data-entry-link="'+esc(e.supersededBy)+'">View correction</a></details>':body;
 }
 function render(story,visual,{details={},originalPlan='',executionPlan='',terminal=''}={}){
  if(!story)return (visual?section('Results &amp; outputs',visual):'')+'<p class="detail-empty" role="status">Loading recorded information…</p>';
  const n=story.state,entries=story.entries||[],active=kind=>entries.filter(e=>e.kind===kind),actions=story.actions||[];
  actionLabels=new Map(actions.map(a=>[a.id,a.label||a.id]));
  const expectedFiles=n.expectedFiles?.length?'<ul class="expected-files">'+n.expectedFiles.map(f=>'<li>'+esc(f)+'</li>').join('')+'</ul>':'';
  const expected=paragraph(n.expectedSummary)+expectedFiles;
  let results='';
  for(const [kind,label] of [['finding','Findings'],['interpretation','Interpretations'],['limitation','Limitations']]){
   results+=item(label,active(kind).map(entry).join(''));
  }
  results+=visual+(details.outputs||'');
  const planned=n.status==='planned';
  let background=item('Scientific question',active('question').map(entry).join(''));
  if(story.archive)background+=paragraph(story.archive.reason);
  if(n.note?.trim()&&!actions.some(a=>a.reason?.trim()===n.note.trim())){
   const attribution=story.annotationAttribution;
   const recorder=attribution?.recordedBy?'Recorded by '+esc(attribution.recordedBy):'';
   const date=attribution?.recordedAt?esc(shortDate(attribution.recordedAt)):'';
   background+=item('Current annotation',paragraph(n.note)+(recorder||date?'<details class="story-evidence"><summary>Attribution</summary><p class="action-meta">'+[recorder,date].filter(Boolean).join(' · ')+'</p></details>':''));
  }
  const limitations=story.workflowProposal?.spec?.limitations||[];
  const proposalLimitations=limitations.length?'<h3>Proposal limitations</h3><ul>'+limitations.map(l=>'<li>'+esc(l)+'</li>').join('')+'</ul>':'';
  let history='';
  if(story.originalPlan){
   const plan=story.originalPlan;
   const meta=[plan.writtenBy?'Proposed by '+esc(plan.writtenBy):'',plan.createdAt?esc(shortDate(plan.createdAt)):''].filter(Boolean).join(' · ');
   const body=originalPlan||paragraph(plan.title)+paragraph(plan.expectedSummary);
   history='<details><summary>Original recorded plan</summary>'+body+(meta?'<p class="action-meta">'+meta+'</p>':'')+'</details>';
  }
  if(executionPlan&&executionPlan!==originalPlan)history+='<details><summary>Plan at execution start</summary>'+executionPlan+'</details>';
  if(!planned&&expected&&(n.expectedSummary!==story.originalPlan?.expectedSummary||
      JSON.stringify(n.expectedFiles||[])!==JSON.stringify(story.originalPlan?.expectedFiles||[]))){
   history+='<details><summary>Expected outputs</summary>'+expected+'</details>';
  }
  for(const a of actions)if(a.reason?.trim())background+='<article class="story-entry"><h3>Stated purpose'+(actions.length>1?' · '+esc(a.label||a.id):'')+'</h3>'+paragraph(a.reason)+'<details class="story-evidence"><summary>Attribution</summary><p class="action-meta">'+(a.writtenBy?'Recorded by '+esc(a.writtenBy)+' · ':'')+esc(a.reasonSource||'Declared purpose')+'</p></details></article>';
  background+=item('Decisions',active('decision').map(entry).join(''));
  for(const e of story.replacements||[])history+='<article class="story-entry"><h3>Replacement relationship</h3><p>'+e.states.map(id=>stateLink(id)).join(' + ')+' → '+stateLink(e.replacementStateId)+'</p>'+entry(e)+'</article>';
  const who=story.participants.length?'<p class="detail-empty">Names and roles are declarations. Recorder identity does not establish approval.</p><ul class="story-people">'+story.participants.map(p=>{
   const context=p.explanationId?'<a href="#explanation-'+esc(p.explanationId)+'" data-entry-link="'+esc(p.explanationId)+'">'+esc(p.context)+'</a>':esc(p.context);
   const meta=[context,p.at?esc(shortDate(p.at)):''].filter(Boolean).join(' · ');
   return '<li><strong>'+esc(p.role)+'</strong> · '+esc(p.name)+(meta?'<small>'+meta+'</small>':'')+'</li>';
  }).join('')+'</ul>':'';
  const labels={'plan.proposed':'Plan proposed','run.started':'Execution started','run.finished':'Execution finished','run.completed':'Execution completed','run.failed':'Execution failed','run.cancelled':'Execution cancelled','run.contact_lost':'Recorder contact lost','workflow.launch_reserved':'Workflow launch reserved','workflow.run_observed':'Workflow run registered','workflow.finished':'Workflow attempt finished','workflow.evidence':'Workflow evidence recorded','workflow.reconciliation_failed':'Workflow reconciliation failed','workflow.contact_lost':'Workflow recorder contact lost','run.command':'Command recorded','flow.edited':'State or relationship edited','flow.undo':'Edit undone','workflow.proposed':'Workflow proposed','workflow.approved':'Workflow approval declared','workflow.cancelled':'Workflow cancelled','reconstruction.proposed':'Reconstruction recorded','reconstruction.reviewed':'Reconstruction reviewed','explanation.recorded':'Explanation or decision recorded'};
  const when=story.timeline.length?'<p class="detail-empty">Dates below are recorder event times. Reported historical dates remain attached to their statements.</p><ol class="story-timeline">'+story.timeline.map(e=>'<li id="event-'+esc(e.revision)+'"><details><summary>'+esc(labels[e.kind]||e.kind.replaceAll('.',' '))+'</summary><pre>'+esc(JSON.stringify(e.payload,null,2))+'</pre></details><p>'+esc(shortDate(e.at))+' · '+esc(e.actor)+' · Event '+esc(e.revision)+'</p></li>').join('')+'</ol>':'';
  history+=item('Participants',who)+item('Timeline',when)+(details.history||'')+terminal;
  if(!planned)results+=proposalLimitations;
  const sections=[
   ['Background &amp; purpose',background],
   ['Results &amp; outputs',results],
   ['Expected outputs',planned?expected+proposalLimitations:''],
   [planned?'Planned inputs':'Inputs',details.inputs],
   [planned?'Proposed method &amp; code':'Method &amp; code',details.method],
  ];
  return sections.filter(([,body])=>body).map(([label,body])=>section(label,body)).join('')+
   (history?'<details class="detail-section detail-card story-section story-history"><summary>History &amp; evidence</summary>'+history+'</details>':'');
 }
 return Object.freeze({render});
}});
