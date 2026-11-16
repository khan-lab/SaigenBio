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
 function observedTool(node){
  const commands=getFlow().actions.filter(a=>a.to===node.id&&a.workflowRun).map(a=>a.command||"").join("\n");
  return /(?:^|\n)\s*python(?:3(?:\.\d+)?)?\s/.test(commands)?"Python":null;
 }
 function method(node){
  const c=context(node);if(!c)return "";
  const tool=observedTool(node)||c.stage?.method?.tool;
  const summary=c.stage?.method?.summary||c.stage?.expectedSummary;
  return [tool,summary].filter(Boolean).join(" · ");
 }
 function card(node){const text=method(node);return text?'<span class="node-method" title="'+esc(text)+'">'+esc(text)+'</span>':"";}
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
  const tool=observedTool(node),declared=stage?.method;
  const inputs=p.spec.inputBindings.map(b=>{const art=flow.artifacts[b.artifactId];return '<li>'+esc(b.name)+' → '+esc(art?.name||b.artifactId)+(art?' · SHA-256 '+esc(art.sha256):"")+'</li>';}).join("");
  return '<section class="detail-section workflow-details"><div class="section-label">Workflow</div><h2>'+esc(pipelineName(p))+'</h2><p>'+esc(engineName(p))+' · '+esc(run?.status||"planned")+'</p>'+
   '<h3>Method</h3><p>'+esc(method(node))+'</p><small>'+esc(tool?tool+' command recorded in the task script. Tool version was not recorded.':declared?.tool?'Tool and method declared in the proposal; execution is not inferred from this description.':'Method described by the proposal. Tool identity was not recorded.')+'</small>'+
   '<h3>'+(p.approval?'Approved parameters':'Proposed parameters')+'</h3><p>'+esc(approval)+'</p><table class="workflow-parameters"><tbody>'+Object.entries(params).map(([k,v])=>row(k,v)).join("")+(Object.keys(params).length?"":row("Parameters","None supplied"))+Object.entries(p.spec.configuration).filter(([k])=>k!=="parameters").map(([k,v])=>row(k,v)).join("")+'</tbody></table><small>Supplied parameter values; pipeline defaults are defined in the preserved source.</small>'+
   '<h3>Recorded inputs</h3><ul class="files">'+inputs+'</ul><h3>Pipeline identity</h3><p>'+esc(displayPath(p.spec.pipeline.source))+'</p><p>Revision: '+esc(p.spec.pipeline.revision)+'</p><p class="workflow-digest">Source SHA-256: '+esc(p.spec.pipeline.contentDigest)+'</p><p class="workflow-digest">Proposal digest: '+esc(p.executionDigest)+'</p>'+
   (run?'<p>Attempt: '+esc(run.id)+'<br>Engine session: '+esc(run.engineRunId||"Not recorded")+'</p>':"")+
   (node.workflowEvidence?'<h3>Execution evidence</h3><p>'+esc(node.workflowEvidence.source)+'</p>'+(node.workflowEvidence.error?'<p class="execution-error">'+esc(node.workflowEvidence.error)+'</p>':"")+'<details><summary>Task observations</summary><pre>'+esc(JSON.stringify(node.workflowEvidence.rows,null,2))+'</pre></details>':"")+
   (declared?.version?'<p>Proposed tool version: '+esc(declared.version)+' (declared)</p>':"")+
   (p.spec.limitations?.length?'<h3>Limitations</h3><ul>'+p.spec.limitations.map(v=>'<li>'+esc(v)+'</li>').join("")+'</ul>':"")+'</section>';
 }
 return Object.freeze({card,preview,labels,details});
}});
