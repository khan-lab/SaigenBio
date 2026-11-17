"use strict";

// State detail presentation only: never infer file dependencies or execute code.
globalThis.SaigenDetails=Object.freeze({create({getFlow,escape:esc,fileRows,displayCommand,displayRecord,displayText,shortDate,workflows}){
 const section=(title,body)=>'<section class="detail-section detail-card"><h2 class="section-label">'+title+'</h2>'+body+'</section>';
 const empty=message=>'<p class="detail-empty">'+message+'</p>';
 const unique=items=>[...new Map(items.filter(Boolean).map(a=>[a.id,a])).values()];
 const files=items=>items.length?'<ul class="files">'+fileRows(items)+'</ul>':empty('No files recorded.');
 function sources(ids){const flow=getFlow();return ids.map(id=>{const n=flow.states.find(s=>s.id===id);return '<button class="source-link" data-open="'+esc(id)+'">'+esc(n?.title||id)+'</button>';}).join(' ');}
 function render(n){
  const flow=getFlow(),actions=flow.actions.filter(a=>a.to===n.id),planned=n.status==='planned',c=workflows.context(n);
  const own=(n.artifactIds||[]).map(id=>flow.artifacts[id]).filter(Boolean);
  const inputIds=actions.flatMap(a=>a.inputArtifacts||[]);
  const inputs=unique((n.status==='imported'&&!n.reconstruction?own:inputIds.map(id=>flow.artifacts[id])).filter(a=>a&&!['code','environment','log'].includes(a.role)&&a.storage!=='reference'));
  const parents=[...new Set(planned?n.planParents||[]:actions.flatMap(a=>a.from||[]))];
  let inputBody=parents.length?'<h3>Source states</h3><div class="detail-sources">'+sources(parents)+'</div>':'';
  if(c){
   inputBody+='<h3>Workflow inputs</h3><p class="detail-empty">Bindings recorded for the whole workflow; individual stage consumption is not established by these bindings.</p>'+files(unique(c.proposal.spec.inputBindings.map(b=>flow.artifacts[b.artifactId])));
  }else inputBody+=planned?empty('File inputs have not been recorded for this plan.'):files(inputs);
  if(n.origin==='terminal')inputBody+=empty('Terminal activity does not establish which files were consumed.');
  let where=section(planned?'Planned inputs':'Inputs',inputBody),how='',result='';
  const explanation=c?workflows.execution(n):null;
  let method='';
  if(explanation){
   method='<p class="method-summary">'+esc((c.run?.stageMethods?.[n.workflowStage]||c.stage?.method)?.summary||'Method explanation not recorded.')+'</p><dl class="method-facts"><dt>Tool</dt><dd>'+esc(explanation.tool)+'</dd><dt>Workflow engine</dt><dd>'+esc(explanation.engine+' '+(c.run?.engine?.version||c.proposal.spec.engine.version))+'</dd></dl><p class="action-meta">Method source: '+esc(explanation.toolSource)+' · proposal recorded by '+esc(c.proposal.writtenBy||'Not recorded')+'</p><p class="action-meta">'+(explanation.engineVerified?'Engine version verified before launch.':'Engine version comes from the proposal; no verification is recorded here.')+'</p>';
   const params=c.proposal.spec.configuration.parameters||{};
   method+='<h3>'+(c.proposal.approval?'Approved parameters':'Proposed parameters')+'</h3><dl class="method-facts">'+Object.entries(params).map(([k,v])=>'<dt>'+esc(k)+'</dt><dd>'+esc(typeof v==='object'?JSON.stringify(v):v)+'</dd>').join('')+'</dl>'+(Object.keys(params).length?'':empty('None supplied.'))+'<p class="detail-empty">Supplied values; pipeline defaults remain in the preserved source.</p>';
  }else if(planned){method='<p class="method-summary">'+esc(n.planDetails||'Proposed method not recorded.')+'</p>';}
  for(const a of actions){
   const explanation=a.code?.explanation;
   if(!c)method+='<p class="method-summary">'+esc(explanation?.summary||'Method explanation not recorded.')+'</p>'+(explanation?'<p class="action-meta">Explanation recorded by '+esc(explanation.recordedBy)+'</p>':'')+(a.environment?.declaredToolVersions?.length?'<p>Declared tools: '+a.environment.declaredToolVersions.map(esc).join(' · ')+'</p>':'');
   method+='<details class="command-details"><summary>Command and key script</summary><h3>'+(a.origin==='reconstructed'?'Reported command':a.status==='planned'?'Proposed command':'Recorded command')+'</h3><pre>'+esc(displayCommand(a))+'</pre>'+
    (explanation?.excerpts||[]).map(e=>'<div class="script-excerpt"><h3>'+esc(flow.artifacts[e.artifactId]?.name||'Script')+' · Lines '+esc(e.start)+'–'+esc(e.end)+'</h3><pre>'+esc(e.text)+'</pre><p class="action-meta">Excerpt selected by '+esc(explanation.recordedBy)+'</p><button class="file-button" data-artifact="'+esc(e.artifactId)+'">Open full preserved script →</button></div>').join('')+
    '<h3>Preserved scripts</h3>'+files(unique((a.code?.scriptArtifacts||[]).map(id=>flow.artifacts[id])))+'</details>';
  }
  if(!method)method=empty(n.status==='imported'?'Existing files were imported; their creation method was not recorded.':'Method explanation not recorded.');
  if(planned&&n.planRequires)method+='<h3>Prerequisite</h3><p>'+esc(n.planRequires)+'</p><p class="detail-empty">Recorded condition; SaigenBio does not enforce it.</p>';
  how+=section(planned?'Proposed method':'Method',method);
  const outputs=own.filter(a=>!['code','environment','log'].includes(a.role)&&a.storage!=='reference');
  let outputBody=planned?'':n.status==='imported'&&!n.reconstruction?empty('This state records existing inputs; no produced files are recorded.'):files(outputs);
  if(n.expectedFiles?.length)outputBody+=(planned?'':'<h3>Expected files</h3>')+'<ul class="expected-files">'+n.expectedFiles.map(f=>'<li>'+esc(f)+'</li>').join('')+'</ul>';
  if(planned&&!n.expectedFiles?.length)outputBody=empty('Expected output files not recorded.');
  if(n.origin==='terminal')outputBody=empty('Files preserved at a terminal checkpoint; production by a particular command is not established.')+files(outputs);
  where+=section(planned?'Expected outputs':n.origin==='terminal'||n.reconstruction?'Preserved files':'Outputs',outputBody);
  const refs=unique([...own,...inputIds.map(id=>flow.artifacts[id])].filter(a=>a?.storage==='reference'));
  if(refs.length||n.references?.length)where+=section('Additional references',empty('References are separate from preserved input and output evidence.')+files(refs)+(n.references||[]).map(v=>'<p>'+esc(displayText(v))+'</p>').join(''));
  if(actions.length||c)how+='<details class="detail-section detail-card execution-details"><summary>Execution details</summary>'+workflows.details(n)+actions.map(a=>'<article class="action-row"><h3>'+esc(a.label||'Execution')+' · '+esc(a.status)+'</h3><p>Recorded by '+esc(a.writtenBy)+' · Executed by '+esc(a.performedBy||'Not recorded')+'</p><p>Started '+esc(shortDate(a.startedAt))+' · Finished '+esc(shortDate(a.finishedAt))+' · Exit '+esc(a.exitCode??'Not recorded')+'</p>'+(a.error?'<p class="execution-error">'+esc(displayText(a.error,a))+'</p>':'')+(a.annotation?'<p>Human note: '+esc(a.annotation)+'</p>':'')+'<h3>Logs</h3>'+files((a.logs||[]).map(id=>flow.artifacts[id]).filter(Boolean))+'<details class="provenance"><summary>Full execution record</summary><pre>'+esc(JSON.stringify(displayRecord(a,a),null,2))+'</pre><button class="exact-command" data-original-command="'+esc(a.id)+'">Original command record</button></details></article>').join('')+'</details>';
  if(n.reconstruction){
   const r=n.reconstruction;
   const evidence=(owner)=>(owner.evidence||[]).map(e=>'<li><strong>'+esc(e.kind)+'</strong> · <button class="file-button" data-artifact="'+esc(e.artifactId)+'">'+esc(flow.artifacts[e.artifactId]?.name||e.source)+'</button> · '+esc(e.location)+'<p>'+esc(e.note)+'</p></li>').join('');
   result=section('Reconstruction '+esc(r.review),'<p>Historical execution was not observed by SaigenBio. Acceptance records your review of the reconstruction.</p><ul>'+evidence(r)+'</ul>'+actions.filter(a=>a.reconstruction).map(a=>'<h3>Relationship: '+esc(a.label)+'</h3><ul>'+evidence(a.reconstruction)+'</ul>').join('')+(r.review==='draft'?'<p>Review all states and connections in this proposal before accepting.</p><button data-reconstruction="'+esc(r.id)+'" data-decision="accept">Accept reconstruction</button> <button data-reconstruction="'+esc(r.id)+'" data-decision="reject">Reject reconstruction</button>':''))+result;
  }
  return result+'<details class="story-support"><summary>How</summary>'+how+'</details><details class="story-support"><summary>Where</summary>'+where+'</details>';
 }
 return Object.freeze({render});
}});
