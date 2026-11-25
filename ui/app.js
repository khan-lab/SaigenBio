
"use strict";

const $ = s => document.querySelector(s);
const esc = value => String(value ?? "").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const copy = value => JSON.parse(JSON.stringify(value));

const {W,H}=SaigenGeometry;
let flow={schemaVersion:1,project:"Project",revision:0,states:[],actions:[],artifacts:{},revisions:[]};
let history=[],selection=new Set(),connecting=null,editorContext=null;
let reports;
let bookmarks=new Set(),savedOnly=false,fullCanvasCamera=null;
let groupView=null,groupDialogEdge=null;
let groupsMode=true,pendingGroupFocus=null;
let camera={x:70,y:90,scale:.72},savedCamera=null,drag=null,hoverTimer=null,hideTimer=null,toastTimer=null;
let ready=false,busy=false,token="",allEvents=[],artifactRequest=0;
const getState=id=>flow.states.find(n=>n.id===id);
const showingSaved=()=>savedOnly&&!reports.active;
const visibleStates=()=>groupView?.states??(showingSaved()?flow.states.filter(n=>bookmarks.has(n.id)):flow.states);
const canvasState=id=>groupView?.byId.get(id)??getState(id);
const getAction=id=>flow.actions.find(a=>a.id===id);
const artifactURL=id=>"/api/artifacts/"+encodeURIComponent(id);
const artifacts=n=>(n.artifactIds||[]).map(id=>flow.artifacts[id]).filter(Boolean);
const unavailablePlots=new Set();
const firstPlot=n=>artifacts(n).find(a=>a.storage==="preserved"&&!unavailablePlots.has(a.id)&&/^image\/(svg\+xml|png|jpeg|webp|gif)$/.test(a.mime));
const firstTable=n=>artifacts(n).find(a=>a.tablePreview);
function tableMarkup(n,mini=false){
 const a=firstTable(n);if(!a)return "";
 const t=a.tablePreview,cols=t.columns.slice(0,mini?3:6),rows=t.rows.slice(0,mini?3:5);
 return '<div class="table-preview"><table><thead><tr>'+cols.map(c=>'<th>'+esc(c)+'</th>').join("")+'</tr></thead><tbody>'+rows.map(r=>'<tr>'+r.slice(0,cols.length).map(c=>'<td>'+esc(c)+'</td>').join("")+'</tr>').join("")+'</tbody></table></div>';
}
const workflows=SaigenWorkflows.create({getFlow:()=>flow,escape:esc,displayPath:(...args)=>displayPath(...args)});
const decisionSummary=n=>(n.note||flow.actions.filter(a=>a.to===n.id).map(a=>a.reason).filter(Boolean).join(" ")).trim();
const shortDate=value=>value?new Date(value).toLocaleString():"Not recorded";
const stamp=n=>n.finishedAt||n.createdAt;
function toast(message){$("#toast").textContent=message;$("#toast").hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$("#toast").hidden=true,3600);}
function newId(prefix){return prefix+"_"+crypto.randomUUID().replaceAll("-","").slice(0,12);}
const request=SaigenAPI.create(()=>token);
async function loadHistory(){
 allEvents=await request("/api/history");
 const undone=new Set(allEvents.filter(e=>e.kind==="flow.undo").map(e=>e.payload.undoOf));
 history=allEvents.filter(e=>e.kind==="flow.edited"&&e.undoable&&!undone.has(e.revision)
   &&!e.payload.operations?.every(op=>op.op==="edit_overview")).map(e=>e.revision);
 $("#undo").disabled=!history.length;
}
function redraw(){
 hideStatePopups();render();
 if(!$("#detail-view").hidden){const top=$("#detail-view").scrollTop;const id=decodeURIComponent(location.hash.slice(7)),n=getState(id)||detailController.state(id);if(n)detailController.render(n);else location.hash="";$("#detail-view").scrollTop=top;}
 $("#intro").hidden=flow.states.length>0;
 $(".project-name").textContent=flow.project;
}
async function accept(next){
 cancelDrag();flow=next;await loadHistory();redraw();
}
async function mutate(operations,undo=null){
 return applyChange(undo?"/api/undo":"/api/edit",undo?{event:undo}:{operations},undo?"Change undone. History preserved.":"Saved to this project.");
}
function saveLayout(operations){
 return applyChange("/api/edit",{operations});
}
async function applyChange(path,body,message){
 if(busy)throw new Error("A change is already being saved.");
 busy=true;
 try{
   const next=await request(path,{...body,revision:flow.revision});
   await accept(next);
   if(message)toast(message);
   return true;
 }catch(error){
   if(error.status===409){await accept(await request("/api/flow"));throw new Error(error.message);}
   throw error;
 }finally{busy=false;}
}
async function start(){
 try{
   const session=await request("/api/session");token=session.token;projectRoot=session.projectRoot||"";
   const [next,preferences]=await Promise.all([request("/api/flow"),request("/api/revision")]);
   bookmarks=new Set(preferences.bookmarks);await accept(next);ready=true;
   renderSavedControls();
   $("#connection").textContent="";$("#connection").hidden=true;
   $("#report-toggle").disabled=false;fit(true);route();
 }catch(error){$("#connection").hidden=false;$("#connection").textContent="Offline";$("#intro p").textContent=error.message;}
}
async function poll(){
 if(busy||drag||$("#editor").open)return;
 try{
   if(!ready){await start();return;}
   const next=await request("/api/revision");
   if(busy||drag)return;
   const reconnected=$("#connection").textContent==="Offline";
   if(reconnected)unavailablePlots.clear();
   const saved=next.bookmarks??[];
   const bookmarksChanged=saved.length!==bookmarks.size||saved.some(id=>!bookmarks.has(id));
   bookmarks=new Set(saved);
   if(next.revision!==flow.revision)await accept(await request("/api/flow"));
   else if(reconnected||bookmarksChanged)redraw();
   $("#connection").textContent="";$("#connection").hidden=true;
 }catch(error){$("#connection").hidden=false;$("#connection").textContent="Offline";$("#connection").title=error.message;}
}
let projectRoot="";
const {displayPath,displayText,displayCommand,displayRecord}=SaigenPaths.create(()=>flow,()=>projectRoot);
function bindOriginalCommands(el){
 el.querySelectorAll("[data-original-command]").forEach(button=>button.onclick=()=>{
   const action=getAction(button.dataset.originalCommand);if(!action)return;
   artifactRequest++;$("#action-preview").hidden=true;
   $("#artifact-title").textContent="Exact local command";
   $("#artifact-body").innerHTML='<p class="action-meta">Original execution record · contains local absolute paths</p><pre>'+esc(action.command||"Command not specified")+'</pre><p class="action-meta">Working directory</p><pre>'+esc(action.cwd||"Not recorded")+'</pre>';
   $("#artifact-dialog").showModal();
 });
}

function imagePreview(n,cls="",loading="lazy"){
 const art=firstPlot(n);return art?'<img class="'+cls+'" data-plot-artifact="'+esc(art.id)+'" data-plot-state="'+esc(n.id)+'" src="'+artifactURL(art.id)+'" alt="'+esc(n.title)+'" loading="'+loading+'">':"";
}
// Summaries compare recorded file contents, never file names or record IDs.
function inputRecords(a){
 return (a.inputArtifacts||[]).map(id=>flow.artifacts[id]).filter(f=>f&&!["code","environment","log"].includes(f.role));
}
function metadataRecords(a){
 const args=a.argv||[],values=[];
 for(let i=0;i<args.length;i++){
   const match=args[i].match(/^(--metadata|--sample-metadata|--sample-sheet)(?:=(.*))?$/);
   if(match)values.push(match[2]??args[++i]??"");
 }
 const inputs=inputRecords(a),files=[];
 for(const value of values){
   const file=inputs.find(f=>value===f.sourcePath||value===f.name||(f.sha256&&value.split(/[\\/]/).at(-1)===f.sha256));
   if(file&&!files.some(f=>f.id===file.id))files.push(file);
 }
 return {declared:values.length>0,files,complete:values.length>0&&values.every(v=>inputs.some(f=>v===f.sourcePath||v===f.name||(f.sha256&&v.split(/[\\/]/).at(-1)===f.sha256)))};
}
function operationKey(a){
 const args=a.argv||[];
 if(!args.length)return null;
 const firstFlag=args.findIndex((v,i)=>i>0&&v.startsWith("-"));
 const prefix=args.slice(0,firstFlag<0?3:Math.min(firstFlag,3)).map(v=>v.split(/[\\/]/).at(-1));
 const tool=args.indexOf("--tool");
 return JSON.stringify([prefix,tool>=0?args[tool+1]?.split(/[\\/]/).at(-1):null]);
}
function contentSignature(files){
 if(!files.length||files.some(f=>!/^[a-f0-9]{64}$/i.test(f.sha256||"")))return null;
 return files.map(f=>f.sha256).sort().join(":");
}
function compareContent(files,otherSets){
 const own=contentSignature(files),others=otherSets.map(contentSignature);
 if(!own||!others.length||others.some(v=>!v))return "unknown";
 return others.every(v=>v===own)?"same":"different";
}
function actionContext(a){
 const metadata=metadataRecords(a),key=operationKey(a);
 const peers=key?flow.actions.filter(b=>b.id!==a.id&&operationKey(b)===key&&b.origin==="recorded"):[];
 const otherMetadata=peers.map(metadataRecords);
 const metadataStatus=metadata.complete&&otherMetadata.every(m=>m.complete)
   ?compareContent(metadata.files,otherMetadata.map(m=>m.files)):"unknown";
 const withoutMetadata=(b,m)=>inputRecords(b).filter(f=>!m.files.some(x=>x.id===f.id));
 return {
   metadata,peers,otherMetadata,metadataStatus,
   inputStatus:compareContent(withoutMetadata(a,metadata),peers.map((b,i)=>withoutMetadata(b,otherMetadata[i]))),
   source:a.from.map(id=>getState(id)?.title||"Unknown state").join(" + ")
 };
}
function comparisonMarkup(a){
 const context=actionContext(a);
 if(!context.metadata.declared||!context.peers.length)return "";
 const otherNames=[...new Set(context.peers.flatMap(p=>p.from.map(id=>getState(id)?.title||"Unknown state")))];
 const status=s=>s==="same"?"same contents":s==="different"?"different contents":"not established";
 let content='<div class="edge-comparison"><p>Compared with '+esc(otherNames.join(" / "))+'</p><div>Input files <strong class="comparison-'+context.inputStatus+'">'+status(context.inputStatus)+'</strong></div><div>Metadata <strong class="comparison-'+context.metadataStatus+'">'+status(context.metadataStatus)+'</strong></div>';
 if(context.metadataStatus==="different"){
   const seen=new Set();
   content+='<div class="metadata-alternatives">Other metadata versions: '+context.otherMetadata.flatMap((m,i)=>m.files.map(f=>({f,peer:context.peers[i]}))).filter(({f})=>!seen.has(f.id)&&seen.add(f.id)).map(({f,peer})=>'<button class="file-button" data-artifact="'+esc(f.id)+'">'+esc(peer.from.map(id=>getState(id)?.title).join(" + ")+" · "+f.name)+'</button>').join(" ")+'</div>';
 }
 return content+'<small>Compared using recorded file checksums.</small></div>';
}
function bindArtifactButtons(el){
 el.querySelectorAll("[data-artifact]").forEach(b=>b.onclick=()=>{el.hidden=true;openArtifact(b.dataset.artifact);});
}

function nodeContent(n){
 if(n.status==="running"||n.status==="planned")return '<span class="node-title">'+esc(n.title)+'</span>'+workflows.card(n)+'<span class="node-bottom">'+(n.status==="running"?"Running":"Planned")+'</span>';
 const plot=firstPlot(n),bad=["failed","cancelled","unknown"].includes(n.status);
 return '<span class="node-title">'+esc(n.title)+'</span>'+workflows.card(n)+(plot?'<span class="mini-plot">'+imagePreview(n)+'</span>':firstTable(n)?tableMarkup(n,true):'<span class="node-excerpt">'+esc(decisionSummary(n))+'</span>')+'<span class="node-bottom">'+(n.reconstruction?"Reconstruction · "+esc(n.reconstruction.review):bad?esc(n.status):n.status==="imported"?"Imported · "+n.files.length+" files":n.files.length+" saved outputs")+'</span>';
}

function reportBadge(id){const i=reports.position(id);return reports.active&&i>=0?'<span class="report-badge" aria-label="Report position '+(i+1)+'">'+(i+1)+'</span>':"";}
function bookmarkButton(n){
 const saved=bookmarks.has(n.id);
 return '<button type="button" class="bookmark" data-bookmark="'+esc(n.id)+'" aria-pressed="'+saved+'" aria-label="Bookmark '+esc(n.title)+'" title="'+(saved?"Remove bookmark":"Bookmark this node")+'"><svg viewBox="0 0 20 20" width="16" height="16" aria-hidden="true"><path d="M5 3h10v14l-5-3.5L5 17z"/></svg></button>';
}
async function toggleBookmark(button){
 if(busy||!ready)return;
 const stateId=button.dataset.bookmark;
 busy=true;button.disabled=true;hidePopups();
 try{
   const {bookmarks:saved}=await request("/api/bookmarks",{stateId,saved:!bookmarks.has(stateId)});
   bookmarks=new Set(saved);redraw();
   if(document.activeElement===document.body){
     const scope=$("#detail-view").hidden?$("#nodes"):$("#detail-content");
     (scope.querySelector('[data-bookmark="'+CSS.escape(stateId)+'"]')||$("#canvas-filter")).focus({preventScroll:true});
   }
 }catch(error){toast(error.message);}
 finally{busy=false;button.disabled=false;}
}
function renderSavedControls(){
 const count=flow.states.filter(n=>bookmarks.has(n.id)).length;
 const active=showingSaved(),filter=$("#canvas-filter");
 filter.disabled=!ready;
 filter.value=$("#archive-dialog").open?"archived":active?"saved":"all";
 $("#filter-saved").textContent="Saved ("+count+")";
 $("#saved-empty").hidden=!active||count>0;
}
function setSavedView(saved){
 if(!ready||busy||saved===savedOnly)return;
 cancelDrag();hidePopups();selection.clear();connecting=null;
 $("#viewport").classList.remove("connecting");
 savedOnly=saved;
 if(savedOnly)fullCanvasCamera={...camera};
 else if(fullCanvasCamera){camera=fullCanvasCamera;fullCanvasCamera=null;}
 render();
 if(savedOnly)fit();
 else applyCamera();
}
function selectedStates(){return flow.states.filter(n=>selection.has(n.id));}
function selectNode(id,additive=false){
 if(additive){if(selection.has(id))selection.delete(id);else selection.add(id);}
 else selection=new Set([id]);
 hidePopups();syncSelection();
}
function syncSelection(){
 selection=new Set([...selection].filter(id=>getState(id)&&!groupView?.endpoint.has(id)&&(!showingSaved()||bookmarks.has(id))));
 $("#viewport").classList.toggle("multi-select",selection.size>1);
 $("#use-pipeline-targets").disabled=!selection.size||!$("#pipeline-session").value;
 $("#nodes").querySelectorAll("[data-state]").forEach(card=>{
   const selected=selection.has(card.dataset.state);
   card.classList.toggle("selected",selected);card.setAttribute("aria-pressed",String(selected));
 });
 const message=selection.size?selection.size+(selection.size===1?" node selected":" nodes selected"):"Selection cleared";
 if($("#selection-status").textContent!==message)$("#selection-status").textContent=message;
 positionSelection();
}
function renderWorkflowLabels(){
 $("#workflow-labels").innerHTML=workflows.labels(groupView?.endpoint,groupView?.byId,showingSaved()?visibleStates():undefined);
 $("#workflow-labels").querySelectorAll("[data-workflow-state]").forEach(b=>b.onclick=()=>openState(b.dataset.workflowState));
}
function renderNodes(){
 renderWorkflowLabels();
 const states=visibleStates();
 $("#nodes").innerHTML=states.map(n=>'<div class="state-slot" style="left:'+n.x+'px;top:'+n.y+'px"><button class="state '+esc(n.status)+(firstPlot(n)?" has-plot":"")+(selection.has(n.id)?" selected":"")+'" data-state="'+esc(n.id)+'" aria-pressed="'+selection.has(n.id)+'" aria-describedby="selection-help" aria-label="'+esc(n.title)+'">'+reportBadge(n.id)+nodeContent(n)+'<span class="port" title="Connect to another state" aria-hidden="true"></span></button>'+(reports.active||connecting?"":bookmarkButton(n))+'</div>').join("")+
   (groupView?.summaries.map(group=>'<div class="analysis-group-slot">'+SaigenAnalysisGroups.card(group,esc,imagePreview)+
     '<button type="button" class="group-preview-trigger" data-preview-group aria-controls="group-preview" aria-expanded="false" aria-label="Preview '+esc(group.title)+'">Preview</button></div>').join("")??"");
 positionGroupCards();
 syncSelection();
}
function positionGroupCards(){
 for(const group of groupView?.summaries??[]){
   const card=$("#nodes").querySelector('[data-analysis-group="'+CSS.escape(group.groupId)+'"]').parentElement;
   Object.assign(card.style,{left:group.x+"px",top:group.y+"px",width:group.width+"px",height:group.height+"px"});
   card.style.setProperty("--group-font-scale",group.fontScale);
 }
}
const {edgeAnchor,edgePath}=SaigenGeometry;
const actionJunction=a=>SaigenGeometry.actionJunction(a,groupView?.placed??flow.states);
function executedScriptName(a){
 const argv=a.argv||a.argvTemplate||[];
 if(!argv.length)return "";
 const base=v=>String(v).split(/[\\/]/).pop();
 const executable=base(argv[0]);
 if(/\.(py|r|sh|bash|zsh|pl|jl)$/i.test(executable))return executable;
 if(!/^(python[\d.]*|Rscript|bash|sh|zsh|perl|julia)$/.test(executable))return "";
 // Only the interpreter's script position; never name a data argument as the executed script.
 for(let i=1;i<argv.length;i++){
   if(["-c","-m","-e"].includes(argv[i]))return "";
   if(argv[i].startsWith("-"))continue;
   return /\.(py|r|sh|bash|zsh|pl|jl)$/i.test(argv[i])?base(argv[i]):"";
 }
 return "";
}
function edgeLabel(a,x,y){
 const context=actionContext(a);
 const label=context.metadata.declared?a.label.replace(/\s*\+\s*metadata\s*$/i,""):a.label;
 const parts=label.split(/\s*[·•]\s*/),rows=[{text:executedScriptName(a)||parts[0],kind:"tool",indent:0}];
 parts.shift();
 for(const part of parts)rows.push({text:part,kind:/^--?\S/.test(part)?"option":"context",indent:10});
 if(context.metadata.declared){
   rows.push({text:"input: "+context.source,kind:"source",indent:8});
   rows.push({text:"metadata: "+(context.peers.length?context.metadataStatus:"recorded"),kind:"metadata "+context.metadataStatus,indent:8});
 }
 const clipped=s=>s.length>21?s.slice(0,20)+"…":s;
 const width=Math.max(...rows.map(r=>clipped(r.text).length*(r.kind==="tool"?6.3:5.6)+r.indent));
 const left=x-width/2,top=y-(rows.length-1)*14;
 return '<text class="edge-label" x="'+left+'" y="'+top+'" text-anchor="start">'+rows.map((r,i)=>{
   const option=r.kind==="option"?r.text.match(/^(--?\S+)\s+(.+)$/):null;
   const content=option?'<tspan class="option-flag">'+esc(option[1])+'</tspan> <tspan class="option-value">'+esc(clipped(option[2]))+'</tspan>':esc(clipped(r.text));
   return '<tspan class="edge-'+r.kind+'" x="'+(left+r.indent)+'" y="'+(top+i*14)+'">'+content+'</tspan>';
 }).join("")+'</text>';
}

function renderEdges(){
 let html='<defs><marker id="arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="5" markerHeight="5" orient="auto"><path d="M1 1L7 4L1 7" fill="none" stroke="#a0b097" stroke-width="1.2"/></marker></defs>';
 const actions=groupView?.actions??(showingSaved()?flow.actions
   .filter(a=>bookmarks.has(a.to))
   .map(a=>({...a,from:a.from.filter(id=>bookmarks.has(id))}))
   .filter(a=>a.from.length):flow.actions);
 for(const a of actions){const t=canvasState(a.to);
 if(a.from.length>1){
   const p=actionJunction(a),running=a.status==="running",planned=a.status==="planned",cls=running?"running-edge":planned?"planned-edge":"";
   const path=(d,arrow=false)=>'<path class="edge-line '+cls+'" d="'+d+'"'+(arrow&&!running?' marker-end="url(#arrow)"':"")+'/><path class="edge-hit" d="'+d+'"/>';
   html+='<g class="edge-group joined-action" data-action="'+esc(a.id)+'" role="button" tabindex="0" aria-label="'+esc(a.label+' from '+a.from.map(id=>getState(id).title).join(' + ')+' to '+t.title)+'">'+p.inputs.map(i=>path(i.d)).join('')+path(p.output,true)+
     '<circle class="edge-junction" cx="'+p.junction.x+'" cy="'+p.junction.y+'" r="3.5"/>'+edgeLabel(a,p.label.x,p.label.y);
   if(running)html+='<g class="particle"><path d="M-12 0H-2M-7 -4L-2 0L-7 4" stroke="#44815e" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" fill="none"/><animateMotion dur="1.4s" repeatCount="indefinite" rotate="auto" path="'+p.output+'"/></g>';
   html+='</g>';continue;
 }
 a.from.forEach((id,index)=>{const s=canvasState(id),p=edgePath(s,t),running=a.status==="running",planned=a.status==="planned";html+='<g class="edge-group" data-action="'+esc(a.id)+'" role="button" tabindex="0" aria-label="'+esc(a.label+' from '+s.title+' to '+t.title)+'"><path class="edge-line '+(running?"running-edge":planned?"planned-edge":"")+'" d="'+p.d+'"'+(!running?' marker-end="url(#arrow)"':"")+'/><path class="edge-hit" d="'+p.d+'"/>';
 if(index===0){const labelY=a.from.length>1?t.y+H/2-23:p.y-20;html+=edgeLabel(a,p.x,labelY+8);}
 if(running)html+='<g class="particle"><path d="M-27 0H-2M-8 -4L-2 0L-8 4" stroke="#44815e" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" fill="none"/><animateMotion dur="2.5s" repeatCount="indefinite" rotate="auto" path="'+p.d+'"/></g>';
 html+='</g>';});}
 if(groupView)html+=groupView.connections.map((edge,index)=>SaigenAnalysisGroups.edge(edge,index,esc)).join("");
 $("#edges").innerHTML=html;
}
function projectGroups(){
 groupView=flow.analysisGroups?.length&&!showingSaved()?SaigenAnalysisGroups.project(flow,{
   full:!groupsMode||reports.active||!!connecting,scale:camera.scale,figureFor:firstPlot
 }):null;
}
function focusProjectedState(stateId){
 if(!stateId)return;
 const hiddenBy=groupView?.endpoint.get(stateId);
 const selector=hiddenBy
   ? '[data-analysis-group="'+CSS.escape(hiddenBy.slice(6))+'"]'
   : '[data-state="'+CSS.escape(stateId)+'"]';
 ($("#nodes").querySelector(selector)||$("#fit")).focus({preventScroll:true});
}
function renderGraph(){
 const focused=document.activeElement;
 const {state:stateId,bookmark}=focused?.dataset??{};
 const groupId=focused?.closest(".analysis-group-slot")?.querySelector("[data-analysis-group]").dataset.analysisGroup;
 groupPreview.close();
 projectGroups();
 renderNodes();renderEdges();
 if($("#groups-dialog").open)renderGroupDialog();
 if(bookmark&&$("#detail-view").hidden)($("#nodes").querySelector('[data-bookmark="'+CSS.escape(bookmark)+'"]')||$("#canvas-filter")).focus({preventScroll:true});
 else focusProjectedState(stateId??groupView?.groups.find(group=>group.id===groupId)?.anchor.id);
}
function render(){
 $("#reconstruction-notice").hidden=!Object.values(flow.reconstructions||{}).some(p=>["draft","partial"].includes(p.status));
 $("#canvas-view-switch").hidden=!flow.analysisGroups?.length||reports.active;
 $("#canvas-filter-control").hidden=reports.active;
 $("#view-groups").setAttribute("aria-pressed",String(groupsMode&&!showingSaved()&&!connecting));
 $("#view-individual").setAttribute("aria-pressed",String(!showingSaved()&&(!groupsMode||!!connecting)));
 reports.render();renderSavedControls();renderGraph();renderPipelineRequests();
 $("#undo").disabled=!history.length;
 $("#auto-arrange").disabled=showingSaved()||(groupView?.placed.length??flow.states.length)<2;
 positionSelection();
}
function applyCamera(scaleChanged=false){
 $("#scene").style.transform="translate("+camera.x+"px,"+camera.y+"px) scale("+camera.scale+")";
 $("#zoom-label").textContent=Math.round(camera.scale*100)+"%";
 if(scaleChanged&&groupView?.summaries.length){
   projectGroups();
   positionGroupCards();renderEdges();
 }
 positionSelection();
}
function bounds(nodes=flow.states){
 if(!nodes.length)return {x:0,y:0,w:1000,h:600};
 const x=Math.min(...nodes.map(n=>n.x)),y=Math.min(...nodes.map(n=>n.y));
 return {x,y,w:Math.max(...nodes.map(n=>n.x+(n.width??W)))-x,h:Math.max(...nodes.map(n=>n.y+(n.height??H)))-y};
}
function centerCanvas(box,scale){
 const viewport=$("#viewport"),w=viewport.clientWidth,h=viewport.clientHeight;
 camera={scale,x:w>box.w*scale?(w-box.w*scale)/2-box.x*scale:65-box.x*scale,
   y:Math.max(90,(h-box.h*scale)/2)-box.y*scale};
}
function fit(initial=false, nodes=null){
 cancelDrag();
 const v=$("#viewport");
 const scaleFor=box=>Math.min(1,Math.max(1,v.clientWidth-100)/box.w,Math.max(1,v.clientHeight-170)/box.h);
 const overview=!nodes&&groupView?.summaries.length;
 let box=bounds(nodes??groupView?.placed??visibleStates()),scale=scaleFor(box);
 // The summary cards have a minimum on-screen size and may grow as scale drops.
 if(overview){
   for(let pass=0;pass<6;pass++){
     camera.scale=scale;projectGroups();
     box=bounds(groupView.placed);
     const next=scaleFor(box);
     if(next>=scale*.995)break;
     scale=next;
   }
   scale=SaigenAnalysisGroups.readableScale(groupView,scale);
   box=SaigenAnalysisGroups.overviewBounds(groupView.placed.map(card=>SaigenAnalysisGroups.cardAtScale(card,scale)));
 }
 if(initial&&!flow.analysisGroups?.length)scale=Math.max(scale,v.clientWidth<800?.67:.62);
 centerCanvas(box,scale);
 applyCamera(true);
}
function zoom(factor,cx,cy){
 cancelDrag();
 const v=$("#viewport").getBoundingClientRect();
 cx=cx??v.width/2;cy=cy??v.height/2;
 const next=Math.max(Math.min(.02,camera.scale),Math.min(1.8,camera.scale*factor)),ratio=next/camera.scale;
 if(ratio===1)return;
 camera.x=cx-(cx-camera.x)*ratio;camera.y=cy-(cy-camera.y)*ratio;camera.scale=next;
 hidePopups();applyCamera(true);
}
function positionSelection(){
 const el=$("#selection-tools"),nodes=selectedStates().map(n=>canvasState(n.id));
 if(reports.active||!nodes.length||!$("#detail-view").hidden||connecting){el.hidden=true;return;}
 const multiple=nodes.length>1;
 $("#single-selection-actions").hidden=multiple;
 $("#selection-count").hidden=!multiple;$("#group-selection-hint").hidden=!multiple||showingSaved();
 $("#selection-count").textContent=nodes.length+" nodes selected";
 const r=$("#viewport").getBoundingClientRect(),x=(Math.min(...nodes.map(n=>n.x))+Math.max(...nodes.map(n=>n.x+W)))/2,y=Math.min(...nodes.map(n=>n.y));
 el.hidden=false;
 const width=el.offsetWidth||230,left=r.left+camera.x+x*camera.scale,top=r.top+camera.y+y*camera.scale;
 el.style.left=Math.max(10,Math.min(innerWidth-width-10,left-width/2))+"px";
 el.style.top=Math.max(r.top+10,Math.min(innerHeight-52,top-43))+"px";
}
function hideStatePopups(){clearTimeout(hoverTimer);clearTimeout(hideTimer);$("#preview").hidden=true;$("#action-preview").hidden=true;}
function hidePopups(){hideStatePopups();groupPreview.close();}
function placePopup(el,rect){el.hidden=false;const pr=el.getBoundingClientRect();let x=rect.right+13;if(x+pr.width>innerWidth-12)x=rect.left-pr.width-13;if(x<12)x=Math.max(12,Math.min(innerWidth-pr.width-12,rect.left));let y=Math.max(85,Math.min(innerHeight-pr.height-15,rect.top));el.style.left=x+"px";el.style.top=y+"px";}

function renderPreview(n){
 const items=artifacts(n),pending=n.status==="running"||n.status==="planned",plot=firstPlot(n),note=decisionSummary(n),el=$("#preview");
 el.dataset.state=n.id;el.classList.toggle("has-plot",!!plot);
 const explanation=(pending?n.expectedSummary||note:note)?(pending?'<div class="preview-label">Expected result</div>':"")+'<p class="preview-note '+(plot?"preview-caption":"preview-summary")+'">'+esc(pending?n.expectedSummary||note:note)+'</p>':"";
 el.innerHTML='<div class="preview-inner preview-heading"><div class="preview-top"><div class="preview-label">'+esc(n.status)+'</div><button class="preview-open" data-open="'+esc(n.id)+'">Show detail <span aria-hidden="true">→</span></button></div><div class="preview-title">'+esc(n.title)+'</div></div>'+
   (plot?'<div class="preview-plot">'+imagePreview(n,"","eager")+'</div>':tableMarkup(n))+
   '<div class="preview-inner preview-context">'+workflows.preview(n)+explanation+'<div class="preview-label">'+(pending?"Expected outputs":n.status==="imported"?"Preserved inputs":"Saved outputs")+'</div><ul class="preview-files">'+(pending?(n.expectedFiles||[]).map(f=>'<li>'+esc(f)+'</li>').join(""):items.slice(0,4).map(a=>'<li>'+esc(a.name)+'</li>').join(""))+'</ul></div>';
}
function showPreview(id,anchor){
 if(reports.active||connecting||drag||!$("#detail-view").hidden)return;
 const n=getState(id);if(!n)return;
 groupPreview.close();renderPreview(n);placePopup($("#preview"),anchor.getBoundingClientRect());
}
function handleImageError(e){
 const img=e.target;if(!(img instanceof HTMLImageElement))return;
 const id=img.dataset.plotArtifact;
 if(!id){
   const message=document.createElement("span");message.className="action-meta";message.textContent="Preview unavailable · inspect the recorded file";img.replaceWith(message);return;
 }
 const affectsGroup=groupView?.summaries.some(group=>group.figure?.artifact.id===id);
 unavailablePlots.add(id);
 // Update only affected cards; the underlying records and canvas position stay intact.
 for(const n of flow.states.filter(n=>(n.artifactIds||[]).includes(id))){
   const node=$("#nodes").querySelector('[data-state="'+CSS.escape(n.id)+'"]');
   if(node){
     node.classList.toggle("has-plot",!!firstPlot(n));
     node.innerHTML=reportBadge(n.id)+nodeContent(n)+'<span class="port" title="Connect to another state" aria-hidden="true"></span>';
   }
   if(!$("#preview").hidden&&$("#preview").dataset.state===n.id)renderPreview(n);
   if(!$("#detail-view").hidden&&decodeURIComponent(location.hash.slice(7))===n.id){
     const top=$("#detail-view").scrollTop;detailController.render(n);$("#detail-view").scrollTop=top;
   }
 }
 if(affectsGroup){cancelDrag();renderGraph();}
}
function showAction(id,anchor){
 hidePopups();const a=getAction(id);if(!a)return;
 const el=$("#action-preview");el.classList.remove("file-popover");
 el.innerHTML='<div class="preview-inner"><button class="close-pop" aria-label="Close action details">×</button><div class="preview-label">'+esc(a.status)+'</div><div class="preview-title">'+esc(a.label)+'</div>'+comparisonMarkup(a)+'<pre>'+esc(displayCommand(a))+'</pre><p class="preview-note">'+esc(a.reason||"Reason not recorded")+'</p>'+(a.annotation?'<p class="preview-note"><strong>Human note:</strong> '+esc(a.annotation)+'</p>':"")+'<div class="action-meta">'+esc(a.methodSource)+'</div><div class="action-meta">'+esc(a.performedBy?"Executor: "+a.performedBy:"No execution recorded")+'</div></div>';
 if(a.recoveredFileInputBindings?.length){
   el.querySelector(".preview-inner").insertAdjacentHTML("beforeend",
     '<p class="action-meta">An input connection was recovered from an exact recorded artifact ID.</p>');
 }
 if(a.from.length>1){
   el.querySelector(".preview-inner").insertAdjacentHTML("beforeend",'<div class="preview-label action-meta">Input states</div><ul class="preview-files">'+a.from.map(id=>'<li><button class="source-link" data-input-state="'+esc(id)+'">'+esc(getState(id).title)+'</button></li>').join('')+'</ul>');
   el.querySelectorAll("[data-input-state]").forEach(b=>b.onclick=()=>{el.hidden=true;openState(b.dataset.inputState);});
 }
 el.querySelector(".preview-inner").insertAdjacentHTML("beforeend",'<button class="quiet edit-action">Edit action</button>');
 el.querySelector(".edit-action").onclick=()=>{el.hidden=true;openActionEditor(a);};
 bindArtifactButtons(el);placePopup(el,anchor.getBoundingClientRect());el.querySelector(".close-pop").onclick=()=>el.hidden=true;
}
function fileRows(items){
 return items.map(a=>'<li><button class="filename mono file-button" data-artifact="'+esc(a.id)+'">'+esc(a.name)+'</button><span class="file-type">'+esc(a.storage==="reference"?"External reference":(a.size/1024).toFixed(1)+" KB")+'</span></li>').join("");
}
function terminalMarkup(activity){
 if(!activity)return "";
 const commands=activity.commands||[];
 return '<details class="provenance terminal-history"><summary>Terminal activity · '+commands.length+' commands</summary><p class="action-meta">'+esc(activity.association)+'</p>'+
 (activity.gaps?.length?'<p class="action-meta">Recording was paused during this step; some activity is missing.</p>':"")+
 commands.map(c=>'<article class="terminal-command"><pre>'+esc(displayText(c.command,c))+'</pre><div class="action-meta">'+
 esc(c.status==="shell-returned"?(c.backgroundPossible?"Shell returned; background completion unverified":"Shell returned"):"Completion unknown")+
 (c.exitCode!==null&&c.exitCode!==undefined?' · Exit '+esc(c.exitCode):"")+
 (c.pipelineExitCodes?.length>1?' · Pipeline exits '+c.pipelineExitCodes.map(esc).join(", "):"")+
 '</div><div class="action-meta">'+esc(shortDate(c.startedAt))+' → '+esc(shortDate(c.finishedAt))+'</div><div class="action-meta mono">'+esc(displayPath(c.cwd,c))+'</div></article>').join("")+'</details>';
}
function planMarkup(p){
 const expected=p.expectedSummary||p.note||"";
 const parents=p.planParents||p.parents||[];
 return (p.title?'<h3>'+esc(p.title)+'</h3>':"")+
   (expected?'<h3>Expected result</h3><p>'+esc(expected)+'</p>':"")+
   (p.planDetails||p.method?.summary?'<h3>Proposed method</h3><p>'+esc(p.planDetails||p.method.summary)+'</p>':"")+
   (p.planRequires?'<h3>Prerequisite</h3><p>'+esc(p.planRequires)+'</p><small>Recorded condition; SaigenBio does not enforce it.</small>':"")+
   (p.note&&p.note!==expected?'<h3>Notes</h3><p>'+esc(p.note)+'</p>':"")+
   (parents.length?'<h3>Planned inputs</h3><p>'+parents.map(id=>'<button class="source-link" data-open="'+esc(id)+'">'+esc(getState(id)?.title||id)+'</button>').join(" + ")+'</p>':"")+
   (p.expectedFiles?.length?'<h3>Expected files</h3><ul class="files">'+p.expectedFiles.map(f=>'<li>'+esc(f)+'</li>').join("")+'</ul>':"");
}
async function openArtifact(id){
 const a=flow.artifacts[id];if(!a)return;
 const requestId=++artifactRequest,el=$("#artifact-dialog");
 $("#artifact-title").textContent=a.name;
 $("#artifact-body").textContent="Loading…";el.showModal();
 try{
   const response=await fetch(artifactURL(id));
   if(!response.ok){const value=await response.json();throw new Error(value.error);}
   if(requestId!==artifactRequest||!el.open)return;
   if(a.mime.startsWith("image/"))$("#artifact-body").innerHTML='<img class="artifact-image" src="'+artifactURL(id)+'" alt="'+esc(a.name)+'">';
   else{const value=await response.text();if(requestId!==artifactRequest||!el.open)return;$("#artifact-body").innerHTML='<pre>'+esc(value.slice(0,200000))+'</pre>'+(value.length>200000?'<p class="action-meta">Preview truncated at 200,000 characters.</p>':"");}
 }catch(error){if(requestId===artifactRequest)$("#artifact-body").textContent=error.message;}
}

function openState(id){hidePopups();if($("#detail-view").hidden)savedCamera={...camera};location.hash="state/"+encodeURIComponent(id);}
const explanationEditor = SaigenExplanationEditor.create({
 query: $, escape: esc, field, getFlow: () => flow, request, accept, toast,
 FormData: globalThis.FormData
});
const detailController = SaigenDetailController.create({
 query: $, escape: esc, getFlow: () => flow, getState, getEvents: () => allEvents,
 getHash: () => location.hash, goBack: () => { location.hash = ""; },
 request, accept, toast, editor: explanationEditor, firstPlot, firstTable,
 imagePreview, tableMarkup, displayText, displayCommand, displayRecord,
 shortDate, fileRows, workflows, planMarkup, terminalMarkup, bindOriginalCommands,
 openStateEditor, openState, openArtifact, bookmarkButton, toggleBookmark,
 groupPath: id => SaigenAnalysisGroups.path(flow.analysisGroups??[],id),
 showGroupMembers: id => showGroupMembers(id),
 activeElement: () => document.activeElement,
 getElementById: id => document.getElementById(id)
});
function route(){
 cancelDrag();
 hidePopups();const match=location.hash.match(/^#state\/(.+)$/);let n;
 try{const id=match?decodeURIComponent(match[1]):null;n=id?(getState(id)||detailController.state(id)):null;
 if(id&&!n){$("#flow-view").hidden=true;$("#detail-view").hidden=false;$("#detail-content").textContent="Loading recorded state…";detailController.load(id);return;}}catch{}
 if(n){$("#flow-view").hidden=true;$("#detail-view").hidden=false;$("#selection-tools").hidden=true;detailController.render(n);$("#detail-view").scrollTop=0;}
 else{
   $("#flow-view").hidden=false;$("#detail-view").hidden=true;
   if(pendingGroupFocus){
     const groupId=pendingGroupFocus;pendingGroupFocus=null;savedCamera=null;
     showGroupMembers(groupId);return;
   }
   const restored=!!savedCamera;
   if(restored){camera={...savedCamera};savedCamera=null;}
   applyCamera(restored);
 }
}
function field(name,label,value="",type="input",placeholder=""){
 const c=type==="textarea"?'<textarea name="'+name+'" rows="3" placeholder="'+esc(placeholder)+'">'+esc(value)+'</textarea>':'<input name="'+name+'" value="'+esc(value)+'" '+(name==="title"||name==="label"?"required":"")+' maxlength="'+(name==="title"?80:1000)+'" placeholder="'+esc(placeholder)+'">';
 return '<label class="field">'+label+c+'</label>';
}
function showEditor(context,title,fields,deletable=false){
 $("#delete-item").textContent="Delete";
 hidePopups();editorContext=context;$("#editor-title").textContent=title;$("#editor-fields").innerHTML=fields;$("#form-error").textContent="";$("#delete-item").hidden=!deletable;$("#editor").showModal();$("#editor-fields input")?.focus();
}

function stateRemoval(n){
 const options=flow.removalOptions;
 const proposal=n.workflowProposal&&!n.workflowRun?n.workflowProposal:null;
 const errors=proposal?options?.proposals:options?.states,key=proposal||n.id;
 const available=errors&&Object.hasOwn(errors,key);
 return {allowed:!!available&&errors[key]===null,reason:available?errors[key]:null,proposal};
}
function openStateEditor(n){
 const removal=stateRemoval(n);
 const planned=n.origin==="manual"&&n.status==="planned";
 showEditor({type:"state",id:n.id},"Edit state",field("title","State name",n.title)+(planned?planFields(n):"")+field("note","Notes",n.note,"textarea")+field("files",planned?"Expected output names · one per line":"Additional file references · one per line",(planned?n.expectedFiles||[]:n.references||[]).join("\n"),"textarea")+'<p class="field-hint">'+(planned?"A plan does not execute a command.":"Saved output files and execution facts stay attached to the original record.")+'</p>'+(removal.reason&&n.status==="planned"?'<p class="field-hint">'+esc(removal.reason)+'</p>':"")+(removal.allowed&&removal.proposal?'<p class="field-hint">Cancels this entire unexecuted workflow and removes all its planned cards. The proposal and approval history are preserved. Cancellation cannot be undone; publish a new proposal to proceed.</p>'+field("cancelReason","Reason for cancelling the workflow","","textarea"):""),removal.allowed);
 $("#delete-item").textContent=removal.proposal?"Cancel workflow":"Delete";
}
function planFields(n={}){
 return field("expectedSummary","Expected result · one short sentence",n.expectedSummary||"","textarea")+field("planDetails","Proposed method",n.planDetails||"","textarea")+field("planRequires","Prerequisite",n.planRequires||"","textarea")+'<p class="field-hint">Prerequisites describe when to proceed; SaigenBio does not enforce them.</p>';
}
function addState(parent=null){
 if(showingSaved())setSavedView(false);
 showEditor({type:"add",parent:parent?.id},parent?"Add a branch":"Add a state",field("title","State name","","input","Short result name")+planFields()+field("note","Notes","","textarea")+field("files","Expected output names · one per line","","textarea")+(parent?field("label","Action label","","input","Script or tool")+field("command","Proposed command","","textarea")+field("reason","Why take this branch?","","textarea"):""));
}
function openActionEditor(a){
 const planned=a.origin==="manual"&&a.status==="planned";
 showEditor({type:"action",id:a.id},"Edit action",field("label","Label on the arrow",a.label)+(planned?field("command","Proposed command",a.command,"textarea")+field("reason","Reason",a.reason,"textarea"):field("annotation","Your note",a.annotation||"","textarea")+'<p class="field-hint">The observed command, reason, status, and executor remain in the original record.</p>'),planned);
}

function startConnecting(id){selection=new Set([id]);connecting=id;hidePopups();$("#viewport").classList.add("connecting");render();}
function connectTo(id){
 const source=getState(connecting),target=getState(id);
 if(!source||!target)return;
 if(target.origin!=="manual"||target.status!=="planned"){toast("Connect to a planned state. Existing execution inputs are preserved.");return;}
 if(source.id===target.id){toast("Choose a different state.");return;}
 if(target.x<source.x+W+25){toast("Place the target to the right of the source first.");return;}
 if(flow.actions.some(a=>a.from.includes(source.id)&&a.to===target.id)){toast("These states are already connected.");return;}
 const seen=new Set();function reaches(n){if(n===source.id)return true;if(seen.has(n))return false;seen.add(n);return flow.actions.filter(a=>a.from.includes(n)).some(a=>reaches(a.to));}
 if(reaches(target.id)){toast("This connection would create a cycle.");return;}
 const from=source.id,to=target.id;connecting=null;$("#viewport").classList.remove("connecting");renderGraph();

 showEditor({type:"connect",from,to},"Connect states",field("label","Label on the arrow","","input","Script or tool")+field("command","Command or action","","textarea")+field("reason","Why are these states connected?","","textarea"));
}
function freePosition(x,y){
 for(let i=0;i<100;i++){if(!flow.states.some(n=>Math.abs(n.x-x)<W+35&&Math.abs(n.y-y)<H+35))return {x,y};y+=175;}return{x,y};
}

$("#editor-form").onsubmit=async e=>{
 e.preventDefault();if(busy)return;
 const data=new FormData(e.currentTarget),v=k=>String(data.get(k)||"").trim(),ctx=editorContext;
 const refs=v("files").split("\n").map(x=>x.trim()).filter(Boolean),ops=[];
 if(ctx.type==="state"){
   const n=getState(ctx.id),changes={title:v("title"),note:v("note")};
   if(n.origin==="manual"&&n.status==="planned")for(const key of ["expectedSummary","planDetails","planRequires"])changes[key]=v(key);
   changes[n.origin==="manual"&&n.status==="planned"?"expectedFiles":"references"]=refs;
   ops.push({op:"edit_state",id:n.id,changes});
 }else if(ctx.type==="action"){
   const a=getAction(ctx.id),changes={label:v("label")};
   if(a.origin==="manual"&&a.status==="planned")Object.assign(changes,{command:v("command"),reason:v("reason")});
   else changes.annotation=v("annotation");
   ops.push({op:"edit_action",id:a.id,changes});
 }else if(ctx.type==="add"){
   const parent=getState(ctx.parent),r=$("#viewport").getBoundingClientRect(),pos=freePosition(parent?parent.x+320:(r.width/2-camera.x)/camera.scale,parent?parent.y+190:(r.height/2-camera.y)/camera.scale),id=newId("st");
   ops.push({op:"add_state",id,value:{title:v("title"),note:v("note"),expectedSummary:v("expectedSummary"),planDetails:v("planDetails"),planRequires:v("planRequires"),x:pos.x,y:pos.y,expectedFiles:refs}});
   if(parent)ops.push({op:"add_action",id:newId("plan"),value:{from:[parent.id],to:id,label:v("label"),command:v("command"),reason:v("reason")}});
   selection=new Set([id]);
 }else if(ctx.type==="connect"){
   ops.push({op:"add_action",id:newId("plan"),value:{from:[ctx.from],to:ctx.to,label:v("label"),command:v("command"),reason:v("reason")}});
 }
 const button=e.currentTarget.querySelector('[type="submit"]');button.disabled=true;
 try{await mutate(ops);$("#editor").close();positionSelection();}
 catch(error){$("#form-error").textContent=error.message;}
 finally{button.disabled=false;}
};
$("#delete-item").onclick=async()=>{
 const ctx=editorContext;
 if(busy)return;
 if(ctx.type==="state"){
  const removal=stateRemoval(getState(ctx.id));
  if(removal.allowed&&removal.proposal){
   const reason=String(new FormData($("#editor-form")).get("cancelReason")||"").trim();
   if(!reason){$("#form-error").textContent="Enter a reason for cancelling the workflow.";return;}
   try{await applyChange("/api/workflows/"+encodeURIComponent(removal.proposal)+"/cancel",{reason},"Workflow cancelled. History preserved.");$("#editor").close();location.hash="";}
   catch(error){$("#form-error").textContent=error.message;}
   return;
  }
 }
 try{await mutate([{op:ctx.type==="state"?"delete_state":"delete_action",id:ctx.id}]);$("#editor").close();if(ctx.type==="state"&&!$("#detail-view").hidden)location.hash="";}
 catch(error){$("#form-error").textContent=error.message;}
};

$("#close-editor").onclick=$("#cancel-editor").onclick=()=>$("#editor").close();
$("#editor").addEventListener("click",e=>{if(e.target===$("#editor")){const r=e.target.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)e.target.close();}});
$("#undo").onclick=async()=>{if(!history.length||busy)return;try{await mutate(null,history.at(-1));}catch(error){toast(error.message);}};
$("#canvas-filter").onchange=async event=>{
 const filter=event.currentTarget;
 if(filter.value==="archived"&&!busy&&ready){
   hidePopups();
   filter.disabled=true;
   try{await detailController.openArchive();}
   finally{renderSavedControls();}
 }else{
   setSavedView(filter.value==="saved");
   renderSavedControls();
 }
};
$("#archive-dialog").addEventListener("close",()=>{
 renderSavedControls();
 if($("#detail-view").hidden)$("#canvas-filter").focus({preventScroll:true});
});
$("#show-all-nodes").onclick=()=>setSavedView(false);
$("#view-groups").onclick=()=>setCanvasView(true);
$("#view-individual").onclick=()=>setCanvasView(false);
$("#auto-arrange").onclick=async()=>{
 if(!ready||busy||drag||reports.active||showingSaved()||flow.states.length<2)return;
 const button=$("#auto-arrange");
 button.disabled=true;
 try{
   const viewport=$("#viewport");
   const layout=groupView?.summaries.length ? SaigenAnalysisGroups.arrange(groupView,camera.scale,{
     width:Math.max(1,viewport.clientWidth-100),height:Math.max(1,viewport.clientHeight-170),
   }) : null;
   const operations=layout
     ? SaigenAnalysisGroups.translate(groupView,layout.cards.map(({id,x,y})=>{
        const card=canvasState(id);return {id,dx:x-card.x,dy:y-card.y};
       }))
     : SaigenGeometry.autoArrange(flow.states,flow.actions)
         .filter(({id,x,y})=>getState(id).x!==x||getState(id).y!==y)
         .map(({id,x,y})=>({op:"edit_state",id,changes:{x,y}}));
   if(operations.length)await saveLayout(operations);
   else toast("The canvas is already arranged.");
   if(layout){centerCanvas(layout.bounds,layout.scale);applyCamera(true);}
   else fit();
 }catch(error){
   toast(error.message);
 }finally{
   button.disabled=showingSaved()||(groupView?.placed.length??flow.states.length)<2;
 }
};
$("#add-state").onclick=()=>addState();
$("#selection-tools").onclick=e=>{if(e.target.closest("#copy-node-ids")){copyNodeIds();return;}if(selection.size!==1)return;const mode=e.target.closest("[data-edit-action]")?.dataset.editAction,n=selectedStates()[0];if(!n)return;if(mode==="edit")openStateEditor(n);if(mode==="branch")addState(n);if(mode==="connect")startConnecting(n.id);};
async function copyNodeIds(){
 const ids=selectedStates().map(node=>node.id);
 if(!ids.length)return;
 const text=ids.join("\n");
 try{
   await navigator.clipboard.writeText(text);
   toast(ids.length===1?"Copied 1 node ID.":"Copied "+ids.length+" node IDs.");
 }catch{
   const field=$("#node-ids-text");
   field.value=text;
   $("#node-ids-dialog").showModal();
   field.focus();field.select();
 }
}
$("#close-node-ids").onclick=()=>$("#node-ids-dialog").close();
$("#fit").onclick=()=>{hidePopups();fit();};
$("#zoom-in").onclick=()=>zoom(1.2);$("#zoom-out").onclick=()=>zoom(1/1.2);
function renderGroupDialog(){
 const edge=groupView?.connections.find(item=>item.from.id===groupDialogEdge?.from.id&&item.to.id===groupDialogEdge?.to.id);
 $("#groups-body").innerHTML=edge?SaigenAnalysisGroups.dependencyList(edge,esc):"<p>This summary connection is no longer visible.</p>";
}
function openGroupDependencies(edge){
 if(reports.active)return;
 hidePopups();groupDialogEdge=edge;renderGroupDialog();$("#groups-dialog").showModal();
}
function inspectAnalysisGroup(summary){
 showGroupMembers(summary.groupId);
}
function setCanvasView(groups,nodes=null){
 if(!ready||busy||reports.active)return;
 cancelDrag();
 hidePopups();
 groupsMode=groups;savedOnly=false;fullCanvasCamera=null;connecting=null;selection.clear();
 $("#viewport").classList.remove("connecting");
 render();
 fit(false,nodes);
}
function showGroupMembers(groupId){
 if(!ready||busy||reports.active)return;
 if(!$("#detail-view").hidden){pendingGroupFocus=groupId;location.hash="";return;}
 const nodes=SaigenAnalysisGroups.memberStates(flow,groupId);
 setCanvasView(false,nodes.length?nodes:null);
 focusProjectedState(nodes[0]?.id);
}
const groupPreview=SaigenGroupPreview.create({
 root:$("#nodes"),panel:$("#group-preview"),getFlow:()=>flow,
 getGroup:id=>groupView?.byId.get("group:"+id),
 enabled:()=>ready&&!busy&&!drag&&!connecting&&!reports.active&&$("#detail-view").hidden,
 openGroup:showGroupMembers,boundsFor:bounds,escape:esc,onShow:hideStatePopups,
});
function pendingPipelineRequests(){
 return Object.values(flow.pipelineExports?.selections??{}).filter(request=>request.status==="pending");
}
function renderPipelineRequests(){
 const requests=pendingPipelineRequests(), control=$("#pipeline-session"), previous=control.value;
 $("#pipeline-banner").hidden=reports.active||!requests.length;
 const placeholder=requests.length>1?'<option value="">Choose an agent request</option>':"";
 control.innerHTML=placeholder+requests.map(item=>'<option value="'+esc(item.id)+'">'+
   esc(item.agent+" · "+shortDate(item.requestedAt)+" · "+item.id.slice(-6))+'</option>').join("");
 if(requests.some(item=>item.id===previous))control.value=previous;
 $("#use-pipeline-targets").disabled=!selection.size||!control.value;
}
$("#pipeline-session").onchange=()=>{
 $("#use-pipeline-targets").disabled=!selection.size||!$("#pipeline-session").value;
};
$("#use-pipeline-targets").onclick=async()=>{
 const button=$("#use-pipeline-targets"), requestId=$("#pipeline-session").value;
 const targets=selectedStates().map(node=>node.id);
 if(busy||reports.active||button.disabled||!requestId||!targets.length)return;
 busy=true;button.disabled=true;
 try{
   await request("/api/pipelines/selections",{request:requestId,targets,revision:flow.revision});
   toast("Results saved for your agent. Return to the same chat to review the pipeline.");
 }catch(failure){
   toast(failure.status===409?"The Canvas changed. Review your selection and try again.":failure.message);
 }finally{busy=false;await poll();renderPipelineRequests();}
};
$("#close-groups").onclick=()=>$("#groups-dialog").close();
$("#groups-body").onclick=e=>{
 const target=e.target.closest("[data-group-target]");
 if(target){$("#groups-dialog").close();openState(target.dataset.groupTarget);}
};
$("#viewport").addEventListener("wheel",e=>{if(e.target.closest("#group-preview"))return;e.preventDefault();const r=e.currentTarget.getBoundingClientRect();zoom(Math.exp(-e.deltaY*.0015),e.clientX-r.left,e.clientY-r.top);},{passive:false});
$("#nodes").addEventListener("pointerover",e=>{const n=e.target.closest("[data-state]");if(reports.active||!n||n.contains(e.relatedTarget))return;clearTimeout(hideTimer);clearTimeout(hoverTimer);hoverTimer=setTimeout(()=>showPreview(n.dataset.state,n),650);});
$("#nodes").addEventListener("keydown",e=>{
 const group=e.target.closest("[data-analysis-group]");
 if(group&&e.shiftKey&&e.key.startsWith("Arrow")){
   e.preventDefault();
   if(!ready||busy||drag||e.repeat)return;
   const node=groupView?.byId.get("group:"+group.dataset.analysisGroup);
   if(!node)return;
   const step=20;
   const dx=step*(Number(e.key==="ArrowRight")-Number(e.key==="ArrowLeft"));
   const dy=step*(Number(e.key==="ArrowDown")-Number(e.key==="ArrowUp"));
   saveLayout(SaigenAnalysisGroups.translate(groupView,[{id:node.id,dx,dy}])).catch(error=>toast(error.message));
   return;
 }
 if(reports.active||connecting||!["Enter"," "].includes(e.key))return;
 const n=e.target.closest("[data-state]");if(!n)return;
 if(e.shiftKey&&e.key===" "){e.preventDefault();selectNode(n.dataset.state,true);return;}
 e.preventDefault();showPreview(n.dataset.state,n);$("#preview [data-open]")?.focus();
});
$("#nodes").addEventListener("pointerout",e=>{const n=e.target.closest("[data-state]");if(!n||n.contains(e.relatedTarget))return;clearTimeout(hoverTimer);hideTimer=setTimeout(()=>$("#preview").hidden=true,150);});
$("#preview").onpointerenter=()=>clearTimeout(hideTimer);
$("#preview").onpointerleave=()=>{hideTimer=setTimeout(()=>$("#preview").hidden=true,150);};
$("#preview").onclick=e=>{const b=e.target.closest("[data-open]");if(b)openState(b.dataset.open);};
let suppressClick=false;
$("#viewport").addEventListener("pointerdown",e=>{
 if(e.button!==0||drag||busy||!ready||e.target.closest("[data-bookmark],[data-preview-group],#group-preview"))return;
 const card=e.target.closest("[data-state]");
 const group=e.target.closest("[data-analysis-group]");
 if(e.target.closest(".port")&&!reports.active){e.preventDefault();startConnecting(card.dataset.state);return;}
 if(e.target.closest(".edge-group,.workflow-label"))return;
 if(connecting&&card)return;
 if(card&&(reports.active||showingSaved()))return;
 // Shift gestures toggle selection on click; they never begin a layout drag.
 if(card&&e.shiftKey){hidePopups();return;}
 const id=group?"group:"+group.dataset.analysisGroup:card?.dataset.state;
 const node=id?canvasState(id):null;
 if(id&&!node)return;
 hidePopups();e.preventDefault();$("#viewport").setPointerCapture(e.pointerId);
 const ids=group?[id]:id?(selection.has(id)?[...selection]:[id]):[];
 const originals=ids.map(id=>canvasState(id)).filter(Boolean).map(n=>({id:n.id,x:n.x,y:n.y}));
 drag={id,originals,startX:e.clientX,startY:e.clientY,x:node?.x??camera.x,y:node?.y??camera.y,
   moved:false,pointerId:e.pointerId,guides:{},group:!!group};
 if(group)group.focus({preventScroll:true});
 if(!node){$("#viewport").classList.add("panning");selection.clear();syncSelection();}
});
function showAlignmentGuides(guides = {}) {
 const vertical = guides.x, horizontal = guides.y;
 $("#alignment-guides").innerHTML =
   (vertical ? `<line x1="${vertical.at}" x2="${vertical.at}" y1="${vertical.start}" y2="${vertical.end}"/>` : "") +
   (horizontal ? `<line x1="${horizontal.start}" x2="${horizontal.end}" y1="${horizontal.at}" y2="${horizontal.at}"/>` : "");
}

function positionStateCard({id,x,y}){
 const card=$("#nodes").querySelector('[data-state="'+CSS.escape(id)+'"]');
 if(card){const slot=card.closest(".state-slot")??card;slot.style.left=x+"px";slot.style.top=y+"px";}
}
function positionDraggedNodes(positions, group = false) {
 for(const {id,x,y} of positions){
   const node=canvasState(id);if(!node)continue;
   node.x=x;node.y=y;
   if(!group)positionStateCard(node);
 }
 if(group)positionGroupCards();
 renderEdges();
 renderWorkflowLabels();
 positionSelection();
}

function moveDrag(clientX, clientY, bypass) {
 const dx = clientX - drag.startX, dy = clientY - drag.startY;
 if (Math.abs(dx) + Math.abs(dy) > 5) drag.moved = true;
 if (!drag.moved) return;
 drag.last = {clientX, clientY};
 if (drag.id) {
   if(drag.group)$("#viewport").classList.add("dragging-group");
   const draggedIds=new Set(drag.originals.map(n=>n.id));
   if(!drag.group){selection=draggedIds;syncSelection();}
   const node=canvasState(drag.id);
   const position = {id: drag.id, x: drag.x + dx/camera.scale, y: drag.y + dy/camera.scale,
     width:node.width,height:node.height};
   const visible=drag.group?groupView.placed:visibleStates();
   const neighbors=visible.filter(n=>!draggedIds.has(n.id));
   const next = SaigenGeometry.alignment(position, neighbors, camera.scale, drag.guides, bypass);
   drag.guides = next.guides;
   const x = next.guides.x ? next.x : Math.round(next.x);
   const y = next.guides.y ? next.y : Math.round(next.y);
   positionDraggedNodes(drag.originals.map(n=>({id:n.id,x:n.x+x-drag.x,y:n.y+y-drag.y})),drag.group);
   showAlignmentGuides(next.guides);
 } else {
   camera.x = drag.x + dx;
   camera.y = drag.y + dy;
   applyCamera();
 }
}

function clearDrag() {
 const current = drag;
 drag = null;
 const viewport = $("#viewport");
 viewport.classList.remove("panning");
 viewport.classList.remove("dragging-group");
 showAlignmentGuides();
 if (viewport.hasPointerCapture(current.pointerId)) viewport.releasePointerCapture(current.pointerId);
 if (current.moved || current.group) {
   suppressClick = true;
   setTimeout(() => suppressClick = false, 50);
 }
 return current;
}

function cancelDrag(event) {
 if (!drag || (event?.pointerId !== undefined && event.pointerId !== drag.pointerId)) return;
 const current = clearDrag();
 if (current.id && current.moved) positionDraggedNodes(current.originals,current.group);
}

$("#viewport").addEventListener("pointermove", e => {
 if (drag?.pointerId === e.pointerId) moveDrag(e.clientX, e.clientY, e.altKey);
});
$("#viewport").addEventListener("pointerup", async e => {
 if (drag?.pointerId !== e.pointerId) return;
 if (drag.moved) moveDrag(e.clientX, e.clientY, e.altKey);
 const current = clearDrag();
 if (!current.id) return;
 // Viewport pointer capture can retarget the eventual click away from the card.
 if (!current.moved) {
   if(current.group)inspectAnalysisGroup(canvasState(current.id));
   else selectNode(current.id);
   return;
 }
 const moved=current.originals.map(original=>({original,node:canvasState(original.id)})).filter(({original,node})=>node&&(node.x!==original.x||node.y!==original.y));
 if(!moved.length)return;
 try {
   const operations=current.group
     ? SaigenAnalysisGroups.translate(groupView,moved.map(({original,node})=>({id:node.id,dx:node.x-original.x,dy:node.y-original.y})))
     : moved.map(({node})=>({op:"edit_state",id:node.id,changes:{x:node.x,y:node.y}}));
   await saveLayout(operations);
 } catch (error) {
   toast(error.message);
   positionDraggedNodes(moved.filter(({node})=>canvasState(node.id)===node).map(({original})=>original),current.group);
 }
});
$("#viewport").addEventListener("pointercancel", cancelDrag);
$("#viewport").addEventListener("lostpointercapture", cancelDrag);
window.addEventListener("blur", cancelDrag);
function updateAlignmentModifier(event) {
 if (event.key === "Alt" && drag?.id && drag.last) {
   moveDrag(drag.last.clientX, drag.last.clientY, event.altKey);
 }
}
document.addEventListener("keyup", updateAlignmentModifier);
$("#nodes").addEventListener("click",e=>{
 const bookmark=e.target.closest("[data-bookmark]");
 if(bookmark){toggleBookmark(bookmark);return;}
 const trigger=e.target.closest("[data-preview-group]");
 if(trigger){
   if(trigger.getAttribute("aria-expanded")==="true")groupPreview.close();
   else groupPreview.show(trigger.parentElement.querySelector("[data-analysis-group]"),"touch",trigger);
   return;
 }
 if(suppressClick||e.target.closest(".port"))return;
 const group=e.target.closest("[data-analysis-group]");
 if(group){
   const summary=groupView.summaries.find(item=>item.groupId===group.dataset.analysisGroup);
   inspectAnalysisGroup(summary);
   return;
 }
 const n=e.target.closest("[data-state]");if(!n)return;
 if(reports.active){reports.toggleState(n.dataset.state);return;}
 if(connecting){connectTo(n.dataset.state);return;}
 selectNode(n.dataset.state,e.shiftKey);
});
function groupConnection(target){
 const edge=target.closest("[data-group-edge]");
 return edge?groupView?.connections[Number(edge.dataset.groupEdge)]:null;
}
$("#edges").addEventListener("click",e=>{
 const summary=groupConnection(e.target);if(summary){openGroupDependencies(summary);return;}
 const g=e.target.closest("[data-action]");if(g){if(e.target.closest(".edge-label,.edge-sub"))showActionFiles(g.dataset.action,e.target);else showAction(g.dataset.action,g);}
});
$("#edges").addEventListener("keydown",e=>{
 if(!["Enter"," "].includes(e.key))return;
 const summary=groupConnection(e.target);
 if(summary){e.preventDefault();openGroupDependencies(summary);return;}
 const g=e.target.closest("[data-action]");if(g){e.preventDefault();showAction(g.dataset.action,g);}
});
document.addEventListener("pointerdown",e=>{if(!e.target.closest("#action-preview")&&!e.target.closest(".edge-group"))$("#action-preview").hidden=true;});
document.addEventListener("keydown",e=>{
 if(e.defaultPrevented)return;
 updateAlignmentModifier(e);
 if(e.key==="Escape"&&document.querySelector('dialog[open]'))return;
 if(e.key==="Escape"&&drag){cancelDrag();selection.clear();syncSelection();return;}
 if(e.key==="Escape"){if(reports.active)reports.setMode(false);hidePopups();const wasConnecting=!!connecting;connecting=null;$("#viewport").classList.remove("connecting");selection.clear();if(wasConnecting)renderGraph();else syncSelection();}
 if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==="z"&&!reports.active&&!e.target.closest("input,textarea")&&!$("#editor").open){e.preventDefault();$("#undo").click();}
});
window.addEventListener("hashchange",route);
window.addEventListener("resize",()=>{hidePopups();applyCamera();});
reports=SaigenReports.create({query:$,getFlow:()=>flow,getToken:()=>token,request,render,hidePopups,
 clearSelection:()=>{cancelDrag();selection.clear();connecting=null;},toast});
render();start();setInterval(poll,1000);
$("#close-artifact").onclick=()=>{artifactRequest++;$("#artifact-dialog").close();};
document.addEventListener("error",handleImageError,true);
window.Saigen={getSnapshot:()=>copy(flow),getCamera:()=>({...camera})};



function actionFiles(a){
 const metadata=new Set(metadataRecords(a).files.map(f=>f.id));
 const outputIds=new Set(getState(a.to)?.artifactIds||[]);
 const inputIds=new Set(a.inputArtifacts||[]);
 const ids=[...(a.code?.scriptArtifacts||[]),...(a.inputArtifacts||[]),...outputIds],seen=new Set();
 return ids.map(id=>flow.artifacts[id]).filter(f=>f&&f.role!=="environment"&&!seen.has(f.id)&&seen.add(f.id)).map(f=>({...f,usage:f.role==="code"?"script":metadata.has(f.id)?"metadata":inputIds.has(f.id)?"input":outputIds.has(f.id)?"output":f.role}));
}
function showActionFiles(id,anchor){
 if(reports.active||connecting||drag)return;
 hidePopups();const a=getAction(id);if(!a)return;
 const files=actionFiles(a),el=$("#action-preview");
 el.classList.add("file-popover");
 el.innerHTML='<div class="preview-inner"><button class="close-pop" aria-label="Close related files">×</button><div class="preview-label">Related files · '+files.length+'</div><div class="preview-title">'+esc(a.label)+'</div>'+comparisonMarkup(a)+(files.length?'<div class="edge-files">'+files.map(f=>'<div class="edge-file"><div class="edge-file-heading"><button class="file-button mono" data-artifact="'+esc(f.id)+'">'+esc(f.name)+'</button><span class="file-type">'+esc(f.usage)+'</span></div><div class="file-path mono">'+esc(displayPath(f.sourcePath,a))+'</div><button class="copy-path" data-path="'+esc(displayPath(f.sourcePath,a))+'">Copy displayed path</button></div>').join("")+'</div><div class="action-meta">Open a name to preview its recorded copy.</div>':'<p class="preview-note">No related files have been recorded for this action.</p>')+'</div>';
 el.querySelector(".close-pop").onclick=()=>{el.hidden=true;};
 bindArtifactButtons(el);
 el.querySelectorAll("[data-path]").forEach(b=>b.onclick=async()=>{try{await navigator.clipboard.writeText(b.dataset.path);toast("Displayed path copied.");}catch{toast("Select and copy the path shown above.");}});
 placePopup(el,anchor.getBoundingClientRect());
}
$("#edges").addEventListener("pointerover",e=>{
 const g=e.target.closest("[data-action]");if(!g||reports.active||connecting||drag)return;
 const label=e.target.closest(".edge-label,.edge-sub"),previous=e.relatedTarget instanceof Element?e.relatedTarget.closest(".edge-label,.edge-sub"):null;
 if(g.contains(e.relatedTarget)&&!!label===!!previous)return;
 clearTimeout(hideTimer);clearTimeout(hoverTimer);
 hoverTimer=setTimeout(()=>label?showActionFiles(g.dataset.action,label):showAction(g.dataset.action,g),650);
});
$("#edges").addEventListener("pointerout",e=>{
 const g=e.target.closest("[data-action]");if(!g||g.contains(e.relatedTarget))return;
 clearTimeout(hoverTimer);hideTimer=setTimeout(()=>$("#action-preview").hidden=true,180);
});
$("#action-preview").onpointerenter=()=>clearTimeout(hideTimer);
$("#action-preview").onpointerleave=()=>{hideTimer=setTimeout(()=>$("#action-preview").hidden=true,180);};
