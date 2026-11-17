"use strict";

// Renders the Engine's attributed story model; never derives scientific conclusions.
globalThis.SaigenStory=Object.freeze({create({escape:esc,shortDate,fileRows}){
 let actionLabels=new Map();
 const empty=label=>'<p class="detail-empty">'+label+' not recorded.</p>';
 const section=(label,body)=>'<section class="detail-section detail-card story-section" aria-label="'+label+'"><h2>'+label+'</h2>'+body+'</section>';
 const stateLink=(id,title=id)=>'<button class="source-link" data-open="'+esc(id)+'">'+esc(title)+'</button>';
 function evidence(refs){return refs.length?'<details class="story-evidence"><summary>Supporting evidence · '+refs.length+'</summary><ul>'+refs.map(r=>'<li>'+(r.type==='artifact'?'<button class="file-button" data-artifact="'+esc(r.id)+'">Source file</button>':r.type==='state'?stateLink(r.id):'<a href="#event-'+esc(r.id)+'" data-event-link="'+esc(r.id)+'">Event '+esc(r.id)+'</a>')+' · '+esc(r.location)+'</li>').join('')+'</ul></details>':empty('Supporting evidence');}
 function entry(e){
  let body='<article class="story-entry" id="explanation-'+esc(e.id)+'"><h3>'+esc(e.summary)+'</h3><p class="action-meta">'+esc(e.evidenceKind)+' statement · recorded by '+esc(e.recordedBy)+' · '+esc(shortDate(e.recordedAt))+'</p>';
  if(e.actions?.length)body+='<p class="action-meta">Applies to: '+e.actions.map(id=>esc(actionLabels.get(id)||id)).join(' · ')+'</p>';
  if(e.historicalAt)body+='<p>Reported historical date: '+esc(shortDate(e.historicalAt))+' <span class="detail-empty">(declared)</span></p>';
  if(e.kind==='decision')body+='<h4>Rationale</h4>'+(e.rationale?'<p>'+esc(e.rationale)+'</p>':empty('Rationale'))+'<h4>Alternatives considered</h4>'+(e.alternatives.length?'<ul>'+e.alternatives.map(a=>'<li>'+esc(a.option)+' — '+esc(a.reason||'Reason not recorded')+'</li>').join('')+'</ul>':empty('Alternatives'))+'<h4>Basis for agreement</h4>'+(e.agreementBasis?'<p>'+esc(e.agreementBasis)+'</p>':empty('Agreement basis'));
  body+=evidence(e.evidence)+'</article>';
  return e.supersededBy?'<details class="story-previous"><summary>Earlier statement (corrected)</summary>'+body+'<a href="#explanation-'+esc(e.supersededBy)+'" data-entry-link="'+esc(e.supersededBy)+'">View correction</a></details>':body;
 }
 function render(story,visual,artifacts){
  if(!story)return ['What','Why','Who','When'].map(label=>section(label,'<p class="detail-empty">Loading recorded information…</p>')).join('');
  const n=story.state,entries=story.entries||[],active=kind=>entries.filter(e=>e.kind===kind),actions=story.actions||[];
  actionLabels=new Map(actions.map(a=>[a.id,a.label||a.id]));
  const expectation=n.expectedSummary||story.originalPlan?.expectedSummary;
  let what=(story.archive?'<p class="story-badge">'+esc(story.archive.label)+'</p><p>'+esc(story.archive.reason||'Reason not recorded')+'</p>':'')+(expectation?'<h3>Intended result</h3><p>'+esc(expectation)+'</p>':empty('Intended result'))+visual;
  const own=(n.artifactIds||[]).map(id=>artifacts[id]).filter(a=>a&&!['code','environment','log'].includes(a.role));
  what+='<h3>'+(n.status==='planned'?'Actual outputs':n.origin==='terminal'||n.reconstruction||n.status==='imported'?'Preserved files':'Recorded outputs')+'</h3>'+(own.length?'<ul class="files">'+fileRows(own)+'</ul>':empty('Actual output files'));
  for(const [kind,label] of [['question','Scientific question'],['finding','Recorded findings'],['interpretation','Interpretations'],['limitation','Limitations']]){
   const values=active(kind);what+='<h3>'+label+'</h3>'+(values.length?values.map(entry).join(''):empty(label));
  }
  if(n.note)what+='<details><summary>Current annotation</summary><p>'+esc(n.note)+'</p><p class="action-meta">Annotation; not automatically classified as a finding. Recorded by '+esc(story.annotationAttribution?.recordedBy||'Not recorded')+' · '+esc(shortDate(story.annotationAttribution?.recordedAt))+'</p></details>';
  const limitations=story.workflowProposal?.spec?.limitations||[];
  if(limitations.length)what+='<h3>Proposal limitations (declared)</h3><ul>'+limitations.map(l=>'<li>'+esc(l)+'</li>').join('')+'</ul>';
  if(story.originalPlan)what+='<details><summary>Original recorded plan</summary><p>'+esc(story.originalPlan.title||'Title not recorded')+'</p><p>'+esc(story.originalPlan.expectedSummary||'Expectation not recorded')+'</p><p class="action-meta">Proposed by '+esc(story.originalPlan.writtenBy||'Not recorded')+' · '+esc(shortDate(story.originalPlan.createdAt))+'</p></details>';
  const decisions=active('decision');
  let why=decisions.length?decisions.map(entry).join(''):empty('Decision rationale, alternatives and agreement basis');
  for(const a of actions)if(a.reason)why+='<article class="story-entry"><h3>Stated purpose · '+esc(a.label||a.id)+'</h3><p>'+esc(a.reason)+'</p><p class="action-meta">Recorded by '+esc(a.writtenBy||'Not recorded')+' · '+esc(a.reasonSource||'Declared purpose')+'</p></article>';
  for(const e of story.replacements||[])why+='<article class="story-entry"><h3>Replacement relationship</h3><p>'+e.states.map(id=>stateLink(id)).join(' + ')+' → '+stateLink(e.replacementStateId)+'</p>'+entry(e)+'</article>';
  let who='<p class="detail-empty">Names and roles are declarations. Recorder identity does not establish approval.</p>';
  who+=story.participants.length?'<ul class="story-people">'+story.participants.map(p=>'<li><strong>'+esc(p.role)+'</strong> · '+esc(p.name)+'<small>'+(p.explanationId?'<a href="#explanation-'+esc(p.explanationId)+'" data-entry-link="'+esc(p.explanationId)+'">'+esc(p.context)+'</a>':esc(p.context))+' · '+esc(shortDate(p.at))+'</small></li>').join('')+'</ul>':empty('Participants');
  if(!story.participants.some(p=>/approv/i.test(p.role)))who+=empty('Agreement participants');
  const labels={'plan.proposed':'Plan proposed','run.started':'Execution started','run.finished':'Execution finished','run.completed':'Execution completed','run.failed':'Execution failed','run.cancelled':'Execution cancelled','run.contact_lost':'Recorder contact lost','workflow.launch_reserved':'Workflow launch reserved','workflow.run_observed':'Workflow run registered','workflow.finished':'Workflow attempt finished','workflow.evidence':'Workflow evidence recorded','workflow.reconciliation_failed':'Workflow reconciliation failed','workflow.contact_lost':'Workflow recorder contact lost','run.command':'Command recorded','flow.edited':'State or relationship edited','flow.undo':'Edit undone','workflow.proposed':'Workflow proposed','workflow.approved':'Workflow approval declared','workflow.cancelled':'Workflow cancelled','reconstruction.proposed':'Reconstruction recorded','reconstruction.reviewed':'Reconstruction reviewed','explanation.recorded':'Explanation or decision recorded'};
  let when='<p class="detail-empty">Dates below are recorder event times. Reported historical dates remain attached to their statements.</p>';
  when+=story.timeline.length?'<ol class="story-timeline">'+story.timeline.map(e=>'<li id="event-'+esc(e.revision)+'"><details><summary>'+esc(labels[e.kind]||e.kind.replaceAll('.',' '))+'</summary><pre>'+esc(JSON.stringify(e.payload,null,2))+'</pre></details><p>'+esc(shortDate(e.at))+' · '+esc(e.actor)+' · Event '+esc(e.revision)+'</p></li>').join('')+'</ol>':empty('Event history');
  return section('What',what)+section('Why',why)+section('Who',who)+section('When',when);
 }
 return Object.freeze({render});
}});
