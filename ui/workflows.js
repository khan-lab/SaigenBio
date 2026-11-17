"use strict";

// Workflow presentation reads approved proposals and observed evidence without editing them.
globalThis.SaigenWorkflows=Object.freeze({create({getFlow,escape:esc,displayPath}){
 function context(node){
  const flow=getFlow(),proposal=flow.workflows?.proposals?.[node.workflowProposal];
  if(!proposal)return null;
  const stage=proposal.spec.stages.find(s=>s.key===node.workflowStage),run=flow.workflows?.runs?.[node.workflowRun];
  return {flow,proposal,stage,run};
 }
 const pipelineName=p=>p.spec.pipeline.name||p.spec.pipeline.source.replace(/[\\/]+$/,"").split(/[\\/]/).pop()||"Workflow";
 const engineName=p=>(p.spec.engine.name==="nextflow"?"Nextflow":p.spec.engine.name)+" "+p.spec.engine.version;
 function execution(node){
  const c=context(node);if(!c)return null;
  const method=c.run?.stageMethods?.[node.workflowStage]||c.stage?.method||{};
  const engine=c.run?.engine||c.proposal.spec.engine;
  return {tool:method.tool||"Tool unknown",version:method.version,summary:method.summary||c.stage?.expectedSummary||"",
   engine:engine.name==="nextflow"?"Nextflow":engine.name,
   engineVerified:c.run?.engine?.source==="version-verified-before-launch",
   toolSource:method.source||"proposal-declared",planned:!c.run};
 }
 function method(node){const e=execution(node);return e?[e.tool,e.summary].filter(Boolean).join(" · "):"";}
 function card(node){
  const e=execution(node);if(!e)return "";
  const provenance=e.planned?"Planned":e.toolSource==="proposal-declared"?"Tool declared":"Tool source: "+e.toolSource;
  const relation=e.tool+" via "+e.engine;
  return '<span class="node-method workflow-executor" title="'+esc(provenance+' · '+relation)+'">'+esc(relation)+'</span><span class="node-method workflow-setting" title="'+esc(provenance+' · '+e.summary)+'">'+esc(e.summary)+'</span>';
 }
 function preview(node){
  const c=context(node);if(!c)return "";
  return '<div class="workflow-preview"><div class="preview-label">'+esc(pipelineName(c.proposal))+' · '+esc(engineName(c.proposal))+'</div><p>'+esc(method(node))+'</p><small>Parameters: '+esc(Object.entries(c.proposal.spec.configuration.parameters||{}).map(([k,v])=>k+' = '+(typeof v==='object'?JSON.stringify(v):String(v))).join(' · ')||'None supplied')+'</small></div>';
 }
 function labels(){
  const groups=new Map();
  for(const node of getFlow().states){if(!context(node))continue;const key=node.workflowRun||node.workflowProposal;if(!groups.has(key))groups.set(key,[]);groups.get(key).push(node);}
  return [...groups.values()].map(nodes=>{
   const node=nodes[0],c=context(node),left=Math.min(...nodes.map(n=>n.x)),top=Math.min(...nodes.map(n=>n.y))-34;
   const status=c.run?.status||(c.proposal.approval?"Approved · awaiting execution":"Proposed · awaiting agreement");
   return '<button class="workflow-label" data-workflow-state="'+esc(node.id)+'" style="left:'+left+'px;top:'+top+'px" title="Review workflow and parameters">'+esc(pipelineName(c.proposal))+' <span>· '+esc(engineName(c.proposal))+' · '+esc(status)+'</span></button>';
  }).join("");
 }
 function details(node){
  const c=context(node);if(!c)return "";
  const {proposal:p,stage,run,flow}=c,params=p.spec.configuration.parameters||{};
  const row=(label,value)=>'<tr><th scope="row">'+esc(label)+'</th><td>'+esc(typeof value==="object"?JSON.stringify(value):String(value))+'</td></tr>';
  const approval=p.approval?"Agreement recorded by "+p.approval.declaredBy+" · "+p.approval.at:"Awaiting user agreement";
  const executionInfo=execution(node),declared=stage?.method;
  const inputs=p.spec.inputBindings.map(b=>{const art=flow.artifacts[b.artifactId];return '<li>'+esc(b.name)+' → '+esc(art?.name||b.artifactId)+(art?' · SHA-256 '+esc(art.sha256):"")+'</li>';}).join("");
  return '<section class="detail-section workflow-details"><div class="section-label">Workflow</div><h2>'+esc(pipelineName(p))+'</h2><p>'+esc(engineName(p))+' · '+esc(run?.status||"planned")+'</p>'+
   '<h3>Method</h3><p>'+esc(executionInfo.tool+' via '+executionInfo.engine+' · '+executionInfo.summary)+'</p><small>'+esc('Tool identity '+(executionInfo.tool==='Tool unknown'?'was not recorded.':'is '+executionInfo.toolSource+'.')+' '+(executionInfo.version?'Tool version '+executionInfo.version+' (declared).':'Tool version was not recorded.')+' '+(executionInfo.engineVerified?'Engine version verified before launch.':executionInfo.planned?'Engine is proposed; execution has not been observed.':'Engine association comes from the saved proposal; this older run has no structured engine verification record.'))+'</small>'+
   '<h3>'+(p.approval?'Approved parameters':'Proposed parameters')+'</h3><p>'+esc(approval)+'</p><table class="workflow-parameters"><tbody>'+Object.entries(params).map(([k,v])=>row(k,v)).join("")+(Object.keys(params).length?"":row("Parameters","None supplied"))+Object.entries(p.spec.configuration).filter(([k])=>k!=="parameters").map(([k,v])=>row(k,v)).join("")+'</tbody></table><small>Supplied parameter values; pipeline defaults are defined in the preserved source.</small>'+
   '<h3>Recorded inputs</h3><ul class="files">'+inputs+'</ul><h3>Pipeline identity</h3><p>'+esc(displayPath(p.spec.pipeline.source))+'</p><p>Revision: '+esc(p.spec.pipeline.revision)+'</p><p class="workflow-digest">Source SHA-256: '+esc(p.spec.pipeline.contentDigest)+'</p><p class="workflow-digest">Proposal digest: '+esc(p.executionDigest)+'</p>'+
   (run?'<p>Attempt: '+esc(run.id)+'<br>Engine session: '+esc(run.engineRunId||"Not recorded")+'</p>':"")+
   (node.workflowEvidence?'<h3>Execution evidence</h3><p>'+esc(node.workflowEvidence.source)+'</p>'+(node.workflowEvidence.error?'<p class="execution-error">'+esc(node.workflowEvidence.error)+'</p>':"")+'<details><summary>Task observations</summary><pre>'+esc(JSON.stringify(node.workflowEvidence.rows,null,2))+'</pre></details>':"")+
   (declared?.version?'<p>Proposed tool version: '+esc(declared.version)+' (declared)</p>':"")+
   (p.spec.limitations?.length?'<h3>Limitations</h3><ul>'+p.spec.limitations.map(v=>'<li>'+esc(v)+'</li>').join("")+'</ul>':"")+'</section>';
 }
 return Object.freeze({card,preview,labels,details,execution,context});
}});
