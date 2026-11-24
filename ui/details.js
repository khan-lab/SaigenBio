"use strict";

// State detail presentation only: never infer file dependencies or execute code.
globalThis.SaigenDetails=Object.freeze({create({getFlow,escape:esc,fileRows,displayCommand,displayRecord,displayText,shortDate,workflows}){
 const section=(title,body)=>body?'<section class="detail-section detail-card"><h2 class="section-label">'+title+'</h2>'+body+'</section>':'';
 const support=(title,body)=>body?'<details class="story-support"><summary>'+title+'</summary>'+body+'</details>':'';
 const contextNote=message=>'<p class="detail-empty">'+message+'</p>';
 const summary=value=>value?.trim()?'<p class="method-summary">'+esc(value)+'</p>':'';
 const unique=items=>[...new Map(items.filter(Boolean).map(a=>[a.id,a])).values()];
 const files=items=>items.length?'<ul class="files">'+fileRows(items)+'</ul>':'';
 function sources(ids){const flow=getFlow();return ids.map(id=>{const n=flow.states.find(s=>s.id===id);return '<button class="source-link" data-open="'+esc(id)+'">'+esc(n?.title||id)+'</button>';}).join(' ');}
 function render(n){
  const flow=getFlow(),actions=flow.actions.filter(a=>a.to===n.id),planned=n.status==='planned',c=workflows.context(n);
  const own=(n.artifactIds||[]).map(id=>flow.artifacts[id]).filter(Boolean);
  const inputIds=actions.flatMap(a=>a.inputArtifacts||[]);
  const inputs=unique((n.status==='imported'&&!n.reconstruction?own:inputIds.map(id=>flow.artifacts[id])).filter(a=>a&&!['code','environment','log'].includes(a.role)&&a.storage!=='reference'));
  const parents=[...new Set(planned?n.planParents||[]:actions.flatMap(a=>a.from||[]))];
  let inputBody=parents.length?'<h3>Source states</h3><div class="detail-sources">'+sources(parents)+'</div>':'';
  if(c){
   const bindings=files(unique(c.proposal.spec.inputBindings.map(b=>flow.artifacts[b.artifactId])));
   if(bindings)inputBody+='<h3>Workflow inputs</h3><p class="detail-empty">Bindings recorded for the whole workflow; individual stage consumption is not established by these bindings.</p>'+bindings;
  }else inputBody+=files(inputs);
  if(inputBody&&n.origin==='terminal')inputBody+=contextNote('Terminal activity does not establish which files were consumed.');
  let where=section(planned?'Planned inputs':'Inputs',inputBody),how='',result='';
  const explanation=c?workflows.execution(n):null;
  let method='';
  if(explanation){
   method=summary((c.run?.stageMethods?.[n.workflowStage]||c.stage?.method)?.summary)+'<dl class="method-facts">'+
    (explanation.tool==='Tool unknown'?'':'<dt>Tool</dt><dd>'+esc(explanation.tool)+'</dd>')+
    '<dt>Workflow engine</dt><dd>'+esc(explanation.engine+' '+(c.run?.engine?.version||c.proposal.spec.engine.version))+'</dd></dl><p class="action-meta">Method source: '+esc(explanation.toolSource)+(c.proposal.writtenBy?' · proposal recorded by '+esc(c.proposal.writtenBy):'')+'</p><p class="action-meta">'+(explanation.engineVerified?'Engine version verified before launch.':'Engine version comes from the proposal; no verification is recorded here.')+'</p>';
   const params=c.proposal.spec.configuration.parameters||{};
   if(Object.keys(params).length)method+='<h3>'+(c.proposal.approval?'Approved parameters':'Proposed parameters')+'</h3><dl class="method-facts">'+Object.entries(params).map(([k,v])=>'<dt>'+esc(k)+'</dt><dd>'+esc(typeof v==='object'?JSON.stringify(v):v)+'</dd>').join('')+'</dl><p class="detail-empty">Supplied values; pipeline defaults remain in the preserved source.</p>';
  }else if(planned)method=summary(n.planDetails);
  for(const a of actions){
   const explanation=a.code?.explanation;
   if(!c)method+=summary(explanation?.summary)+(explanation?.recordedBy?'<p class="action-meta">Explanation recorded by '+esc(explanation.recordedBy)+'</p>':'')+(a.environment?.declaredToolVersions?.length?'<p>Declared tools: '+a.environment.declaredToolVersions.map(esc).join(' · ')+'</p>':'');
   const command=a.command?.trim()||a.argv?.length?'<h3>'+(a.origin==='reconstructed'?'Reported command':a.status==='planned'?'Proposed command':'Recorded command')+'</h3><pre>'+esc(displayCommand(a))+'</pre>':'';
   const scripts=files(unique((a.code?.scriptArtifacts||[]).map(id=>flow.artifacts[id])));
   const commandDetails=command+
    (explanation?.excerpts||[]).map(e=>'<div class="script-excerpt"><h3>'+esc(flow.artifacts[e.artifactId]?.name||'Script')+' · Lines '+esc(e.start)+'–'+esc(e.end)+'</h3><pre>'+esc(e.text)+'</pre><p class="action-meta">Excerpt selected by '+esc(explanation.recordedBy)+'</p><button class="file-button" data-artifact="'+esc(e.artifactId)+'">Open full preserved script →</button></div>').join('')+
    (scripts?'<h3>Preserved scripts</h3>'+scripts:'');
   if(commandDetails)method+='<details class="command-details"><summary>Command and key script</summary>'+commandDetails+'</details>';
  }
  if(planned&&n.planRequires)method+='<h3>Prerequisite</h3><p>'+esc(n.planRequires)+'</p><p class="detail-empty">Recorded condition; SaigenBio does not enforce it.</p>';
  how+=section(planned?'Proposed method':'Method',method);
  const outputs=own.filter(a=>!['code','environment','log'].includes(a.role)&&a.storage!=='reference');
  let outputBody=planned||(n.status==='imported'&&!n.reconstruction)?'':files(outputs);
  if(n.expectedFiles?.length)outputBody+=(planned?'':'<h3>Expected files</h3>')+'<ul class="expected-files">'+n.expectedFiles.map(f=>'<li>'+esc(f)+'</li>').join('')+'</ul>';
  if(n.origin==='terminal'&&outputs.length)outputBody=contextNote('Files preserved at a terminal checkpoint; production by a particular command is not established.')+files(outputs);
  where+=section(planned?'Expected outputs':n.origin==='terminal'||n.reconstruction?'Preserved files':'Outputs',outputBody);
  const refs=unique([...own,...inputIds.map(id=>flow.artifacts[id])].filter(a=>a?.storage==='reference'));
  if(refs.length||n.references?.length)where+=section('Additional references',contextNote('References are separate from preserved input and output evidence.')+files(refs)+(n.references||[]).map(v=>'<p>'+esc(displayText(v))+'</p>').join(''));
  if(actions.length||c)how+='<details class="detail-section detail-card execution-details"><summary>Execution details</summary>'+workflows.details(n)+actions.map(a=>{
   const actors=[a.writtenBy?'Recorded by '+esc(a.writtenBy):'',a.performedBy?'Executed by '+esc(a.performedBy):''].filter(Boolean).join(' · ');
   const times=[a.startedAt?'Started '+esc(shortDate(a.startedAt)):'',a.finishedAt?'Finished '+esc(shortDate(a.finishedAt)):'',a.exitCode!=null?'Exit '+esc(a.exitCode):''].filter(Boolean).join(' · ');
   const logs=files((a.logs||[]).map(id=>flow.artifacts[id]).filter(Boolean));
   return '<article class="action-row"><h3>'+esc(a.label||'Execution')+(a.status?' · '+esc(a.status):'')+'</h3>'+
    (actors?'<p>'+actors+'</p>':'')+(times?'<p>'+times+'</p>':'')+
    (a.error?'<p class="execution-error">'+esc(displayText(a.error,a))+'</p>':'')+
    (a.annotation?'<p>Human note: '+esc(a.annotation)+'</p>':'')+(logs?'<h3>Logs</h3>'+logs:'')+
    '<details class="provenance"><summary>Full execution record</summary><pre>'+esc(JSON.stringify(displayRecord(a,a),null,2))+'</pre>'+
    (a.command?.trim()||a.argv?.length?'<button class="exact-command" data-original-command="'+esc(a.id)+'">Original command record</button>':'')+'</details></article>';
  }).join('')+'</details>';
  if(globalThis.SaigenReconstruction)result+=SaigenReconstruction.create({getFlow,escape:esc,shortDate}).render(n);
  return result+support('How',how)+support('Where',where);
 }
 return Object.freeze({render});
}});
