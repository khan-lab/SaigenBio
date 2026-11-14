
"use strict";

const $ = s => document.querySelector(s);
const esc = value => String(value ?? "").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const copy = value => JSON.parse(JSON.stringify(value));

const W=192,H=132;
let flow={schemaVersion:1,project:"Project",revision:0,states:[],actions:[],artifacts:{},revisions:[]};
let history=[],selected=null,connecting=null,editorContext=null;
let reportMode=false,reportSelection=[],reportJob=null,reportRendering=false;
let camera={x:70,y:90,scale:.72},savedCamera=null,drag=null,hoverTimer=null,hideTimer=null,toastTimer=null;
let ready=false,busy=false,token="",allEvents=[],artifactRequest=0;
const getState=id=>flow.states.find(n=>n.id===id);
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
const decisionSummary=n=>(n.note||flow.actions.filter(a=>a.to===n.id).map(a=>a.reason).filter(Boolean).join(" ")).trim();
const shortDate=value=>value?new Date(value).toLocaleString():"Not recorded";
const stamp=n=>n.finishedAt||n.createdAt;
function toast(message){$("#toast").textContent=message;$("#toast").hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$("#toast").hidden=true,3600);}
function newId(prefix){return prefix+"_"+crypto.randomUUID().replaceAll("-","").slice(0,12);}
async function request(path,body){
 const response=await fetch(path,{method:body?"POST":"GET",headers:body?{"Content-Type":"application/json","X-Saigen-Token":token}:{},body:body?JSON.stringify(body):undefined});
 let value;try{value=await response.json();}catch{throw new Error("The local recorder returned an invalid response.");}
 if(!response.ok){const error=new Error(value.error||"The request failed.");error.status=response.status;throw error;}
 return value;
}
async function loadHistory(){
 allEvents=await request("/api/history");
 const undone=new Set(allEvents.filter(e=>e.kind==="flow.undo").map(e=>e.payload.undoOf));
 history=allEvents.filter(e=>e.kind==="flow.edited"&&e.undoable&&!undone.has(e.revision)).map(e=>e.revision);
 $("#undo").disabled=!history.length;
}
function redraw(){
 hidePopups();render();
 if(!$("#detail-view").hidden){const top=$("#detail-view").scrollTop;const n=getState(decodeURIComponent(location.hash.slice(7)));if(n)renderDetail(n);else location.hash="";$("#detail-view").scrollTop=top;}
 $("#intro").hidden=flow.states.length>0;
 $(".project-name").textContent=flow.project;
}
async function accept(next){
 flow=next;await loadHistory();redraw();
}
async function mutate(operations,undo=null){
 if(busy)throw new Error("A change is already being saved.");
 busy=true;
 try{
   const next=await request(undo?"/api/undo":"/api/edit",undo?{revision:flow.revision,event:undo}:{revision:flow.revision,operations});
   await accept(next);toast(undo?"Change undone. History preserved.":"Saved to this project.");
   return true;
 }catch(error){
   if(error.status===409){await accept(await request("/api/flow"));throw new Error(error.message);}
   throw error;
 }finally{busy=false;}
}
async function start(){
 try{
   const session=await request("/api/session");token=session.token;projectRoot=session.projectRoot||"";
   await accept(await request("/api/flow"));ready=true;
   $("#connection").textContent="";$("#connection").hidden=true;
   $("#report-toggle").disabled=false;fit(true);route();
 }catch(error){$("#connection").hidden=false;$("#connection").textContent="Offline";$("#intro p").textContent=error.message;}
}
async function poll(){
 if(busy||drag||$("#editor").open)return;
 try{
   if(!ready){await start();return;}
   const next=await request("/api/revision");
   const reconnected=$("#connection").textContent==="Offline";
   if(reconnected)unavailablePlots.clear();
   if(next.revision!==flow.revision)await accept(await request("/api/flow"));
   else if(reconnected)redraw();
   $("#connection").textContent="";$("#connection").hidden=true;
 }catch(error){$("#connection").hidden=false;$("#connection").textContent="Offline";$("#connection").title=error.message;}
}
// Path abbreviations affect presentation only; the execution record is untouched.
let projectRoot="",externalDirectories=new Map();
const absolutePath=v=>typeof v==="string"&&/^(?:\/(?!\/)|[A-Za-z]:[\\/]|\\\\)/.test(v);
const slashPath=v=>String(v||"").replace(/\\/g,"/").replace(/\/+$/,"");
const pathBase=v=>slashPath(v).split("/").at(-1);
const pathParent=v=>slashPath(v).split("/").slice(0,-1).join("/");
const below=(path,root)=>!!root&&root!=="/"&&(path===root||path.startsWith(root+"/"));
function pathRoots(action){
 const roots=[],add=(root,alias)=>{root=slashPath(root);if(root&&root!=="/"&&!roots.some(r=>r.root===root))roots.push({root,alias});};
 const inferred=flow.actions.map(a=>a.cwd).find(p=>p&&slashPath(p).includes("/.saigen/runs/"));
 add(action?.cwd&&slashPath(action.cwd).includes("/.saigen/runs/")?action.cwd:"","{run}");
 add(projectRoot||(inferred?slashPath(inferred).split("/.saigen/runs/")[0]:""),".");
 const repositories=[...new Set([...flow.actions.map(a=>a.code?.repository),...flow.states.map(n=>n.code?.repository)].filter(Boolean))].sort();
 repositories.forEach((root,i)=>add(root,repositories.length===1?"{source}":"{source:"+(i+1)+"}"));
 const scriptDirs=[...new Set(Object.values(flow.artifacts).filter(f=>f.role==="code"&&absolutePath(f.sourcePath)).map(f=>pathParent(f.sourcePath)))].sort().filter(dir=>!roots.some(r=>below(dir,r.root)));
 scriptDirs.forEach((root,i)=>add(root,scriptDirs.length===1?"{scripts}":"{scripts:"+(i+1)+"}"));
 return roots.sort((a,b)=>b.root.length-a.root.length);
}
function displayPath(value,action){
 if(!absolutePath(value))return String(value??"");
 const path=slashPath(value),match=pathRoots(action).find(r=>below(path,r.root));
 if(match)return match.alias+path.slice(match.root.length);
 const dir=pathParent(path);
 if(!externalDirectories.has(dir))externalDirectories.set(dir,externalDirectories.size+1);
 return "{external:"+externalDirectories.get(dir)+"}/"+pathBase(path);
}
function displayText(value,action){
 let out=String(value??"");
 for(const {root,alias} of pathRoots(action)){
   const escaped=root.replace(/[.*+?^$(){}|[\]\\]/g,"\\$&");
   out=out.replace(new RegExp('(^|[\\s="\\x27(])'+escaped+'(?=$|[/\\\\\\s"\\x27,;()\\]}])',"g"),(_,lead)=>lead+alias);
 }
 out=out.replace(/(["'])((?:\/(?!\/)|[A-Za-z]:[\\/])[^"'\r\n<>|;&]+)\1/g,(_,quote,path)=>quote+displayPath(path,action)+quote);
 return out.replace(/(^|[\s="'(])((?:\/(?!\/)|[A-Za-z]:[\\/])[^\s"'<>|;&)]+)/g,(_,lead,path)=>lead+displayPath(path,action));
}
function displayArgument(value,action,index){
 if(index===0&&absolutePath(value))return pathBase(value);
 if(absolutePath(value))return displayPath(value,action);
 const assignment=value.match(/^([^=]+=)((?:\/(?!\/)|[A-Za-z]:[\\/]).+)$/);
 return assignment?assignment[1]+displayPath(assignment[2],action):displayText(value,action);
}
function shellQuote(value){
 return /^[a-zA-Z0-9_./:{}=@,+%-]+$/.test(value)?value:"'"+value.replace(/'/g,"'\\''")+"'";
}
function displayCommand(action){
 if(action.terminal)return action.terminal.commands.map(c=>displayText(c.command,c)).join("\n")||"No shell commands in this saved step";
 if(!Array.isArray(action.argv)||!action.argv.length)return displayText(action.command||"Command not specified",action);
 return action.argv.map((value,i)=>{
   const prefix=i===0?"":/^--?[a-zA-Z]/.test(value)?" \\\n  ":" ";
   return prefix+shellQuote(displayArgument(value,action,i));
 }).join("");
}
function displayRecord(value,action,key=""){
 if(Array.isArray(value))return key==="argv"?value.map((v,i)=>displayArgument(v,action,i)):value.map(v=>displayRecord(v,action));
 if(value&&typeof value==="object"){
   const context=Array.isArray(value.argv)?value:action;
   return Object.fromEntries(Object.entries(value).map(([k,v])=>[k,displayRecord(v,context,k)]));
 }
 if(typeof value==="string"){
   if(["sourcePath","cwd","repository","executable","workdir"].includes(key))return displayPath(value,action);
   if(key==="command"&&action?.argv)return displayCommand(action);
   return displayText(value,action);
 }
 return value;
}
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
 if(n.status==="running"||n.status==="planned")return '<span class="ring">'+(n.status==="running"?"↗":"·")+'</span><span class="node-title">'+esc(n.title)+'</span><span class="node-bottom">'+(n.status==="running"?"Running":"Planned")+'</span>';
 const plot=firstPlot(n),bad=["failed","cancelled","unknown"].includes(n.status);
 return '<span class="node-title">'+esc(n.title)+'</span>'+(plot?'<span class="mini-plot">'+imagePreview(n)+'</span>':firstTable(n)?tableMarkup(n,true):'<span class="node-excerpt">'+esc(decisionSummary(n))+'</span>')+'<span class="node-bottom">'+(bad?esc(n.status):n.status==="imported"?"Imported · "+n.files.length+" files":n.files.length+" saved outputs")+'</span>';
}

function reportBadge(id){const i=reportSelection.indexOf(id);return reportMode&&i>=0?'<span class="report-badge" aria-label="Report position '+(i+1)+'">'+(i+1)+'</span>':"";}
function renderNodes(){
 $("#planned-help").hidden=!flow.states.some(n=>n.status==="planned");
 $("#nodes").innerHTML=flow.states.map(n=>'<button class="state '+esc(n.status)+(firstPlot(n)?" has-plot":"")+(selected===n.id?" selected":"")+'" data-state="'+esc(n.id)+'" style="left:'+n.x+'px;top:'+n.y+'px" aria-label="'+esc(n.title)+'">'+reportBadge(n.id)+nodeContent(n)+'<span class="port" title="Connect to another state" aria-hidden="true"></span></button>').join("");
}
function edgePath(from,to){const special=n=>n.status==="running"||n.status==="planned",x1=from.x+(special(from)?from.status==="running"?134:126:W),y1=from.y+(special(from)?46:H/2),x2=to.x+(special(to)?to.status==="running"?58:66:0),y2=to.y+(special(to)?46:H/2),dx=Math.max(35,(x2-x1)*.5);return {d:"M "+x1+" "+y1+" C "+(x1+dx)+" "+y1+", "+(x2-dx)+" "+y2+", "+x2+" "+y2,x:(x1+x2)/2,y:(y1+y2)/2};}
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
 for(const a of flow.actions){const t=getState(a.to);a.from.forEach((id,index)=>{const s=getState(id),p=edgePath(s,t),running=a.status==="running",planned=a.status==="planned";html+='<g class="edge-group" data-action="'+esc(a.id)+'" role="button" tabindex="0" aria-label="'+esc(a.label+' from '+s.title+' to '+t.title)+'"><path class="edge-line '+(running?"running-edge":planned?"planned-edge":"")+'" d="'+p.d+'"'+(!running?' marker-end="url(#arrow)"':"")+'/><path class="edge-hit" d="'+p.d+'"/>';
 if(index===0){const labelY=a.from.length>1?t.y+H/2-23:p.y-20;html+=edgeLabel(a,p.x,labelY+8);}
 if(running)html+='<g class="particle"><path d="M-27 0H-2M-8 -4L-2 0L-8 4" stroke="#44815e" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" fill="none"/><animateMotion dur="2.5s" repeatCount="indefinite" rotate="auto" path="'+p.d+'"/></g>';
 html+='</g>';});}
 $("#edges").innerHTML=html;
}
function render(){renderReport();renderNodes();renderEdges();$("#undo").disabled=!history.length;positionSelection();}
function applyCamera(){ $("#scene").style.transform="translate("+camera.x+"px,"+camera.y+"px) scale("+camera.scale+")";$("#zoom-label").textContent=Math.round(camera.scale*100)+"%";positionSelection();}
function bounds(){const ns=flow.states;if(!ns.length)return {x:0,y:0,w:1000,h:600};const x=Math.min(...ns.map(n=>n.x)),y=Math.min(...ns.map(n=>n.y));return {x,y,w:Math.max(...ns.map(n=>n.x+W))-x,h:Math.max(...ns.map(n=>n.y+H))-y};}
function fit(initial=false){const v=$("#viewport"),b=bounds(),w=v.clientWidth,h=v.clientHeight;let scale=Math.min(1,(w-100)/b.w,(h-170)/b.h);if(initial)scale=Math.max(scale,w<800?.67:.62);scale=Math.max(.22,scale);camera={scale,x:w>b.w*scale?(w-b.w*scale)/2-b.x*scale:65-b.x*scale,y:Math.max(90,(h-b.h*scale)/2)-b.y*scale};applyCamera();}
function zoom(factor,cx,cy){const v=$("#viewport").getBoundingClientRect();cx=cx??v.width/2;cy=cy??v.height/2;const next=Math.max(.22,Math.min(1.8,camera.scale*factor)),ratio=next/camera.scale;camera.x=cx-(cx-camera.x)*ratio;camera.y=cy-(cy-camera.y)*ratio;camera.scale=next;hidePopups();applyCamera();}
function positionSelection(){const el=$("#selection-tools"),n=getState(selected);if(reportMode||!n||!$("#detail-view").hidden||connecting){el.hidden=true;return;}const r=$("#viewport").getBoundingClientRect(),left=r.left+camera.x+(n.x+W/2)*camera.scale,top=r.top+camera.y+n.y*camera.scale;el.hidden=false;el.style.left=Math.max(10,Math.min(innerWidth-250,left-115))+"px";el.style.top=Math.max(r.top+10,Math.min(innerHeight-52,top-43))+"px";}
function hidePopups(){clearTimeout(hoverTimer);clearTimeout(hideTimer);$("#preview").hidden=true;$("#action-preview").hidden=true;}
function placePopup(el,rect){el.hidden=false;const pr=el.getBoundingClientRect();let x=rect.right+13;if(x+pr.width>innerWidth-12)x=rect.left-pr.width-13;if(x<12)x=Math.max(12,Math.min(innerWidth-pr.width-12,rect.left));let y=Math.max(85,Math.min(innerHeight-pr.height-15,rect.top));el.style.left=x+"px";el.style.top=y+"px";}

function renderPreview(n){
 const items=artifacts(n),pending=n.status==="running"||n.status==="planned",plot=firstPlot(n),note=decisionSummary(n),el=$("#preview");
 el.dataset.state=n.id;el.classList.toggle("has-plot",!!plot);
 const explanation=(pending?n.expectedSummary||note:note)?(pending?'<div class="preview-label">Expected result</div>':"")+'<p class="preview-note '+(plot?"preview-caption":"preview-summary")+'">'+esc(pending?n.expectedSummary||note:note)+'</p>':"";
 el.innerHTML='<div class="preview-inner preview-heading"><div class="preview-label">'+esc(n.status)+'</div><div class="preview-title">'+esc(n.title)+'</div></div>'+
   (plot?'<div class="preview-plot">'+imagePreview(n,"","eager")+'</div>':tableMarkup(n))+
   '<div class="preview-inner preview-context">'+explanation+'<div class="preview-label">'+(pending?"Expected outputs":n.status==="imported"?"Preserved inputs":"Saved outputs")+'</div><ul class="preview-files">'+(pending?(n.expectedFiles||[]).map(f=>'<li>'+esc(f)+'</li>').join(""):items.slice(0,4).map(a=>'<li>'+esc(a.name)+'</li>').join(""))+'</ul></div><button class="preview-open" data-open="'+esc(n.id)+'">Show detail <span>→</span></button>';
}
function showPreview(id,anchor){
 if(reportMode||connecting||drag||!$("#detail-view").hidden)return;
 const n=getState(id);if(!n)return;
 renderPreview(n);placePopup($("#preview"),anchor.getBoundingClientRect());
}
function handleImageError(e){
 const img=e.target;if(!(img instanceof HTMLImageElement))return;
 const id=img.dataset.plotArtifact;
 if(!id){
   const message=document.createElement("span");message.className="action-meta";message.textContent="Preview unavailable · inspect the recorded file";img.replaceWith(message);return;
 }
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
     const top=$("#detail-view").scrollTop;renderDetail(n);$("#detail-view").scrollTop=top;
   }
 }
}
function showAction(id,anchor){
 hidePopups();const a=getAction(id);if(!a)return;
 const el=$("#action-preview");el.classList.remove("file-popover");
 el.innerHTML='<div class="preview-inner"><button class="close-pop" aria-label="Close action details">×</button><div class="preview-label">'+esc(a.status)+'</div><div class="preview-title">'+esc(a.label)+'</div>'+comparisonMarkup(a)+'<pre>'+esc(displayCommand(a))+'</pre><p class="preview-note">'+esc(a.reason||"Reason not recorded")+'</p>'+(a.annotation?'<p class="preview-note"><strong>Human note:</strong> '+esc(a.annotation)+'</p>':"")+'<div class="action-meta">'+esc(a.methodSource)+'</div><div class="action-meta">'+esc(a.performedBy?"Executor: "+a.performedBy:"No execution recorded")+'</div></div>';
 el.querySelector(".preview-inner").insertAdjacentHTML("beforeend",'<button class="quiet edit-action">Edit action</button>');
 el.querySelector(".edit-action").onclick=()=>{el.hidden=true;openActionEditor(a);};
 bindArtifactButtons(el);placePopup(el,anchor.getBoundingClientRect());el.querySelector(".close-pop").onclick=()=>el.hidden=true;
}
function fileRows(items){
 return items.map(a=>'<li><button class="filename mono file-button" data-artifact="'+esc(a.id)+'">'+esc(a.name)+'</button><span class="file-type">'+esc(a.storage==="reference"?"External reference":(a.size/1024).toFixed(1)+" KB")+'</span></li>').join("");
}
function stateHistory(n){
 const related=new Set([n.id,...flow.actions.filter(a=>a.to===n.id).map(a=>a.id)]);
 const events=allEvents.filter(e=>e.payload.state?.id===n.id||e.payload.action?.to===n.id||e.payload.operations?.some(op=>related.has(op.id))||e.payload.actions?.some(id=>related.has(id)));
 return '<details class="history"><summary>History · '+events.length+' records</summary>'+events.slice().reverse().map(e=>'<details class="history-event"><summary>'+esc(e.kind.replaceAll("."," "))+' · '+esc(e.actor)+' <span>'+esc(shortDate(e.at))+'</span></summary><pre>'+esc(JSON.stringify(displayRecord(e.payload),null,2))+'</pre></details>').join("")+'</details>';
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
function planMarkup(n){
 const p=n.status==="planned"?n:n.plan;
 if(!p)return "";
 const expected=p.expectedSummary||p.note||"";
 const parents=(p.planParents||[]).map(id=>getState(id)).filter(Boolean);
 return '<section class="detail-section plan-details"><div class="section-label">'+(n.status==="planned"?"Plan":"Original plan")+'</div>'+
   (expected?'<h3>Expected result</h3><p>'+esc(expected)+'</p>':"")+
   (p.planDetails?'<h3>Proposed method</h3><p>'+esc(p.planDetails)+'</p>':"")+
   (p.planRequires?'<h3>Prerequisite</h3><p>'+esc(p.planRequires)+'</p><small>Recorded condition; SaigenBio does not enforce it.</small>':"")+
   (p.note&&p.note!==expected?'<h3>Notes</h3><p>'+esc(p.note)+'</p>':"")+
   (parents.length?'<h3>Planned inputs</h3><p>'+parents.map(s=>'<button class="source-link" data-open="'+esc(s.id)+'">'+esc(s.title)+'</button>').join(" + ")+'</p>':"")+
   (p.expectedFiles?.length?'<h3>Expected files</h3><ul class="files">'+p.expectedFiles.map(f=>'<li>'+esc(f)+'</li>').join("")+'</ul>':"")+'</section>';
}
function renderDetail(n){
 if(!n)return;
 const incoming=flow.actions.filter(a=>a.to===n.id),items=artifacts(n),plot=firstPlot(n),pending=["running","planned"].includes(n.status);
 let visual="";
 if(plot)visual='<figure class="figure"><div class="figure-title">'+esc(plot.name)+'</div>'+imagePreview(n,"detail-image")+'<figcaption>Preserved output · SHA-256 '+esc(plot.sha256.slice(0,16))+'…</figcaption></figure>';
 else if(firstTable(n))visual=tableMarkup(n);
 else if(pending)visual='<div class="run-display"><div class="preview-label">'+esc(n.status)+'</div><p>'+(n.status==="running"?"The recorder is waiting for the command to finish.":"This is a plan. No command has been executed.")+'</p></div>';
 else if(["failed","cancelled","unknown"].includes(n.status))visual='<div class="run-display"><div class="preview-label">'+esc(n.status)+'</div><p>'+esc(displayText(incoming.find(a=>a.error)?.error||"This attempt did not produce a verified completion record."))+'</p></div>';
 const origin=n.status==="planned"?(n.origin==="manual"?"This is a human-supplied plan. No execution has been recorded.":"This is an agent-proposed plan. No execution has been recorded."):n.origin==="terminal"?"Selected files were preserved at this checkpoint. Command order records session activity; it does not establish file dependencies.":n.status==="imported"?"Existing files were recorded. Their earlier execution is not established by this import.":"Execution status was observed by the recorder. A successful command does not establish scientific correctness.";
 $("#detail-content").innerHTML='<nav class="detail-nav"><button class="back" id="back-flow">← Back to flow</button><button class="quiet" id="edit-detail">Edit state</button></nav><div class="detail-kicker">'+esc(n.status)+'</div><h1 class="detail-title">'+esc(n.title)+'</h1><p class="detail-note">'+esc(n.status==="planned"?"":n.note)+'</p><div class="detail-meta"><span class="mono">'+(n.codeRef?"Code "+esc(n.codeRef.slice(0,12))+(n.code?.dirty?" + working changes":""):"Code version not recorded")+'</span><span>Recorded by '+esc(n.writtenBy)+'</span><span>'+esc(shortDate(stamp(n)))+'</span></div>'+visual+
 planMarkup(n)+(n.status!=="planned"?'<section class="detail-section"><div class="section-label">'+(n.status==="imported"?"Saved inputs":"Saved outputs")+'</div><ul class="files">'+(items.length?fileRows(items):'<li>No output files recorded.</li>')+'</ul>': '<section class="detail-section">')+
 (n.status!=="planned"&&n.expectedFiles?.length?'<div class="action-meta">Expected: '+n.expectedFiles.map(esc).join(", ")+'</div>':"")+
 (n.references?.length?'<div class="action-meta">Additional references · not verified: '+n.references.map(v=>esc(displayText(v))).join(", ")+'</div>':"")+'</section>'+
 '<section class="detail-section"><div class="section-label">'+(incoming.length?"How this state is reached":n.status==="planned"?"Execution":"Starting evidence")+'</div>'+
 incoming.map(a=>'<article class="action-row"><div class="action-heading"><span>From '+a.from.map(id=>'<button class="source-link" data-open="'+esc(id)+'">'+esc(getState(id).title)+'</button>').join(" + ")+'</span><span class="preview-label">'+esc(a.status)+'</span></div><pre>'+esc(displayCommand(a))+'</pre><p><strong>Stated reason:</strong> '+esc(a.reason||"Not recorded")+'</p>'+(a.annotation?'<p><strong>Human note:</strong> '+esc(a.annotation)+'</p>':"")+'<div class="action-meta">Recorded by '+esc(a.writtenBy)+' · '+(a.performedBy?"Executed by "+esc(a.performedBy):"No execution recorded")+'</div><div class="action-meta">Started '+esc(shortDate(a.startedAt))+' · Finished '+esc(shortDate(a.finishedAt))+(a.exitCode!==null&&a.exitCode!==undefined?" · Exit "+esc(a.exitCode):"")+'</div>'+(a.error?'<p class="execution-error">'+esc(displayText(a.error,a))+'</p>':"")+(a.logs?.length?'<ul class="files log-files">'+fileRows(a.logs.map(id=>flow.artifacts[id]).filter(Boolean))+'</ul>':"")+(a.origin==="recorded"?'<details class="provenance"><summary>Code, inputs, and environment</summary><pre>'+esc(JSON.stringify(displayRecord({argv:a.argv,cwd:a.cwd,inputArtifacts:a.inputArtifacts,code:a.code,environment:a.environment},a),null,2))+'</pre><button class="exact-command" data-original-command="'+esc(a.id)+'">Exact local command</button></details>':"")+'</article>').join("")+'<p class="origin-note">'+esc(origin)+'</p></section>'+terminalMarkup(n.terminal)+stateHistory(n);
 bindOriginalCommands($("#detail-content"));
 $("#back-flow").onclick=()=>location.hash="";
 $("#edit-detail").onclick=()=>openStateEditor(n);
 $("#detail-content").querySelectorAll("[data-open]").forEach(b=>b.onclick=()=>openState(b.dataset.open));
 $("#detail-content").querySelectorAll("[data-artifact]").forEach(b=>b.onclick=()=>openArtifact(b.dataset.artifact));
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

function openState(id){if(!getState(id))return;hidePopups();if($("#detail-view").hidden)savedCamera={...camera};location.hash="state/"+encodeURIComponent(id);}
function route(){
 hidePopups();const match=location.hash.match(/^#state\/(.+)$/);let n;
 try{n=match?getState(decodeURIComponent(match[1])):null;}catch{}
 if(n){$("#flow-view").hidden=true;$("#detail-view").hidden=false;$("#selection-tools").hidden=true;renderDetail(n);$("#detail-view").scrollTop=0;}
 else{$("#flow-view").hidden=false;$("#detail-view").hidden=true;if(savedCamera){camera={...savedCamera};savedCamera=null;}applyCamera();}
}
function field(name,label,value="",type="input",placeholder=""){
 const c=type==="textarea"?'<textarea name="'+name+'" rows="3" placeholder="'+esc(placeholder)+'">'+esc(value)+'</textarea>':'<input name="'+name+'" value="'+esc(value)+'" '+(name==="title"||name==="label"?"required":"")+' maxlength="'+(name==="title"?80:1000)+'" placeholder="'+esc(placeholder)+'">';
 return '<label class="field">'+label+c+'</label>';
}
function showEditor(context,title,fields,deletable=false){
 hidePopups();editorContext=context;$("#editor-title").textContent=title;$("#editor-fields").innerHTML=fields;$("#form-error").textContent="";$("#delete-item").hidden=!deletable;$("#editor").showModal();$("#editor-fields input")?.focus();
}

function openStateEditor(n){
 const planned=n.origin==="manual"&&n.status==="planned";
 showEditor({type:"state",id:n.id},"Edit state",field("title","State name",n.title)+(planned?planFields(n):"")+field("note","Notes",n.note,"textarea")+field("files",planned?"Expected output names · one per line":"Additional file references · one per line",(planned?n.expectedFiles||[]:n.references||[]).join("\n"),"textarea")+'<p class="field-hint">'+(planned?"A plan does not execute a command.":"Saved output files and execution facts stay attached to the original record.")+'</p>',planned);
}
function planFields(n={}){
 return field("expectedSummary","Expected result · one short sentence",n.expectedSummary||"","textarea")+field("planDetails","Proposed method",n.planDetails||"","textarea")+field("planRequires","Prerequisite",n.planRequires||"","textarea")+'<p class="field-hint">Prerequisites describe when to proceed; SaigenBio does not enforce them.</p>';
}
function addState(parent=null){
 showEditor({type:"add",parent:parent?.id},parent?"Add a branch":"Add a state",field("title","State name","","input","Short result name")+planFields()+field("note","Notes","","textarea")+field("files","Expected output names · one per line","","textarea")+(parent?field("label","Action label","","input","Script or tool")+field("command","Proposed command","","textarea")+field("reason","Why take this branch?","","textarea"):""));
}
function openActionEditor(a){
 const planned=a.origin==="manual"&&a.status==="planned";
 showEditor({type:"action",id:a.id},"Edit action",field("label","Label on the arrow",a.label)+(planned?field("command","Proposed command",a.command,"textarea")+field("reason","Reason",a.reason,"textarea"):field("annotation","Your note",a.annotation||"","textarea")+'<p class="field-hint">The observed command, reason, status, and executor remain in the original record.</p>'),planned);
}

function startConnecting(id){selected=id;connecting=id;hidePopups();$("#viewport").classList.add("connecting");render();}
function connectTo(id){
 const source=getState(connecting),target=getState(id);
 if(!source||!target)return;
 if(target.origin!=="manual"||target.status!=="planned"){toast("Connect to a planned state. Existing execution inputs are preserved.");return;}
 if(source.id===target.id){toast("Choose a different state.");return;}
 if(target.x<source.x+W+25){toast("Place the target to the right of the source first.");return;}
 if(flow.actions.some(a=>a.from.includes(source.id)&&a.to===target.id)){toast("These states are already connected.");return;}
 const seen=new Set();function reaches(n){if(n===source.id)return true;if(seen.has(n))return false;seen.add(n);return flow.actions.filter(a=>a.from.includes(n)).some(a=>reaches(a.to));}
 if(reaches(target.id)){toast("This connection would create a cycle.");return;}
 const from=source.id,to=target.id;connecting=null;$("#viewport").classList.remove("connecting");

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
   selected=id;
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
 try{await mutate([{op:ctx.type==="state"?"delete_state":"delete_action",id:ctx.id}]);$("#editor").close();if(ctx.type==="state"&&!$("#detail-view").hidden)location.hash="";}
 catch(error){$("#form-error").textContent=error.message;}
};

$("#close-editor").onclick=$("#cancel-editor").onclick=()=>$("#editor").close();
$("#editor").addEventListener("click",e=>{if(e.target===$("#editor")){const r=e.target.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)e.target.close();}});
$("#undo").onclick=async()=>{if(!history.length||busy)return;try{await mutate(null,history.at(-1));}catch(error){toast(error.message);}};
$("#add-state").onclick=()=>addState();
$("#selection-tools").onclick=e=>{const mode=e.target.closest("[data-edit-action]")?.dataset.editAction,n=getState(selected);if(!n)return;if(mode==="edit")openStateEditor(n);if(mode==="branch")addState(n);if(mode==="connect")startConnecting(n.id);};
$("#fit").onclick=()=>{hidePopups();fit();};
$("#zoom-in").onclick=()=>zoom(1.2);$("#zoom-out").onclick=()=>zoom(1/1.2);
$("#viewport").addEventListener("wheel",e=>{e.preventDefault();const r=e.currentTarget.getBoundingClientRect();zoom(Math.exp(-e.deltaY*.0015),e.clientX-r.left,e.clientY-r.top);},{passive:false});
$("#nodes").addEventListener("pointerover",e=>{const n=e.target.closest("[data-state]");if(reportMode||!n||n.contains(e.relatedTarget))return;clearTimeout(hideTimer);clearTimeout(hoverTimer);hoverTimer=setTimeout(()=>showPreview(n.dataset.state,n),650);});
$("#nodes").addEventListener("keydown",e=>{
 if(reportMode||connecting||!["Enter"," "].includes(e.key))return;
 const n=e.target.closest("[data-state]");if(!n)return;
 e.preventDefault();showPreview(n.dataset.state,n);$("#preview [data-open]")?.focus();
});
$("#nodes").addEventListener("pointerout",e=>{const n=e.target.closest("[data-state]");if(!n||n.contains(e.relatedTarget))return;clearTimeout(hoverTimer);hideTimer=setTimeout(()=>$("#preview").hidden=true,150);});
$("#preview").onpointerenter=()=>clearTimeout(hideTimer);
$("#preview").onpointerleave=()=>{hideTimer=setTimeout(()=>$("#preview").hidden=true,150);};
$("#preview").onclick=e=>{const b=e.target.closest("[data-open]");if(b)openState(b.dataset.open);};
let suppressClick=false;
$("#viewport").addEventListener("pointerdown",e=>{
 if(e.button!==0||busy||!ready)return;
 const card=e.target.closest("[data-state]");
 if(e.target.closest(".port")&&!reportMode){e.preventDefault();startConnecting(card.dataset.state);return;}
 if(e.target.closest(".edge-group"))return;
 if(connecting&&card)return;
 if(card&&reportMode)return;
 hidePopups();e.preventDefault();$("#viewport").setPointerCapture(e.pointerId);
 drag={id:card?.dataset.state||null,startX:e.clientX,startY:e.clientY,x:card?getState(card.dataset.state).x:camera.x,y:card?getState(card.dataset.state).y:camera.y,moved:false,before:card?copy(flow):null};
 if(!card){$("#viewport").classList.add("panning");selected=null;positionSelection();}
});
$("#viewport").addEventListener("pointermove",e=>{
 if(!drag)return;const dx=e.clientX-drag.startX,dy=e.clientY-drag.startY;if(Math.abs(dx)+Math.abs(dy)>5)drag.moved=true;
 if(!drag.moved)return;
 if(drag.id){const n=getState(drag.id);n.x=Math.round(drag.x+dx/camera.scale);n.y=Math.round(drag.y+dy/camera.scale);const el=$("#nodes").querySelector('[data-state="'+CSS.escape(drag.id)+'"]');el.style.left=n.x+"px";el.style.top=n.y+"px";renderEdges();positionSelection();}
 else{camera.x=drag.x+dx;camera.y=drag.y+dy;applyCamera();}
});

async function endDrag(e){
 if(!drag)return;
 const d=drag;drag=null;$("#viewport").classList.remove("panning");
 if($("#viewport").hasPointerCapture(e.pointerId))$("#viewport").releasePointerCapture(e.pointerId);
 if(d.moved){
   suppressClick=true;setTimeout(()=>suppressClick=false,50);
   if(d.id){selected=d.id;const n=getState(d.id);try{await mutate([{op:"edit_state",id:d.id,changes:{x:n.x,y:n.y}}]);}catch(error){toast(error.message);await accept(await request("/api/flow"));}}
 }else if(d.id){selected=d.id;render();}
}

$("#viewport").addEventListener("pointerup",endDrag);
$("#viewport").addEventListener("pointercancel",endDrag);
$("#nodes").addEventListener("click",e=>{
 if(suppressClick||e.target.closest(".port"))return;const n=e.target.closest("[data-state]");if(!n)return;
 if(reportMode){toggleReportState(n.dataset.state);return;}
 if(connecting){connectTo(n.dataset.state);return;}
 selected=n.dataset.state;render();
});
$("#edges").addEventListener("click",e=>{const g=e.target.closest("[data-action]");if(g){if(e.target.closest(".edge-label,.edge-sub"))showActionFiles(g.dataset.action,e.target);else showAction(g.dataset.action,g);}});
$("#edges").addEventListener("keydown",e=>{if(e.key==="Enter"||e.key===" "){const g=e.target.closest("[data-action]");if(g){e.preventDefault();showAction(g.dataset.action,g);}}});
document.addEventListener("pointerdown",e=>{if(!e.target.closest("#action-preview")&&!e.target.closest(".edge-group"))$("#action-preview").hidden=true;});
document.addEventListener("keydown",e=>{
 if(e.key==="Escape"){if(reportMode)setReportMode(false);hidePopups();if(connecting){connecting=null;$("#viewport").classList.remove("connecting");}else selected=null;positionSelection();}
 if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==="z"&&!reportMode&&!e.target.closest("input,textarea")&&!$("#editor").open){e.preventDefault();$("#undo").click();}
});
window.addEventListener("hashchange",route);
window.addEventListener("resize",()=>{hidePopups();applyCamera();});
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
 if(reportMode||connecting||drag)return;
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
 const g=e.target.closest("[data-action]");if(!g||reportMode||connecting||drag)return;
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

function setReportMode(value){
 reportMode=value;selected=null;connecting=null;
 $("#viewport").classList.remove("connecting");
 $("#viewport").classList.toggle("editing",!value);
 $("#edit-tools").hidden=value;
 if(value)location.hash="";else reportSelection=[];
 hidePopups();$("#report-toggle").setAttribute("aria-pressed",String(value));
 $("#viewport").classList.toggle("report-mode",value);render();
}
function toggleReportState(id){
 if(reportRendering)return;
 invalidateReport();
 reportSelection=reportSelection.includes(id)?reportSelection.filter(x=>x!==id):[...reportSelection,id];
 hidePopups();render();
}
function invalidateReport(){
 if(reportRendering)return;
 reportJob=null;$("#report-status").textContent="";
 $("#report-pdf").hidden=true;$("#report-source").hidden=true;
}
function renderReport(){
 reportSelection=reportSelection.filter(id=>getState(id));
 $("#report-tools").hidden=!reportMode;
 $("#report-count").textContent=reportSelection.length?reportSelection.length+(reportSelection.length===1?" state":" states")+" · click to add or remove":"Select states in report order";
 $("#report-create").disabled=!reportSelection.length||reportRendering;
 $("#report-clear").disabled=reportRendering;
}
$("#report-toggle").onclick=()=>setReportMode(!reportMode);
$("#report-cancel").onclick=()=>setReportMode(false);
$("#report-clear").onclick=()=>{invalidateReport();reportSelection=[];render();};
$("#report-create").onclick=async()=>{
 reportRendering=true;reportJob=null;renderReport();
 $("#report-pdf").hidden=true;$("#report-source").hidden=true;
 $("#report-status").textContent="Preparing PDF…";
 try{
  const job=await request("/api/reports",{revision:flow.revision,selected:[...reportSelection]});reportJob=job.id;
  await watchReport();
 }catch(error){reportRendering=false;$("#report-status").textContent=error.message;renderReport();}
};
async function watchReport(){
 try{
  const response=await fetch("/api/reports/"+reportJob,{headers:{"X-Saigen-Token":token}});
  const job=await response.json();if(!response.ok)throw new Error(job.error);
  if(job.status==="ready"){
   reportRendering=false;$("#report-status").textContent="Ready · revision "+job.revision+(job.warnings.length?" · "+job.warnings.length+" figure warning(s)":"");
   $("#report-pdf").hidden=false;$("#report-source").hidden=false;renderReport();return;
  }
  if(job.status==="failed")throw new Error(job.error);
  $("#report-status").textContent="Rendering PDF…";setTimeout(watchReport,1000);
 }catch(error){reportRendering=false;$("#report-status").textContent=error.message;renderReport();}
}
async function downloadReport(kind){
 try{
  const response=await fetch("/api/reports/"+reportJob+"/"+kind,{headers:{"X-Saigen-Token":token}});
  if(!response.ok)throw new Error((await response.json()).error);
  const url=URL.createObjectURL(await response.blob()),link=document.createElement("a");
  link.href=url;link.download="saigen-report."+kind;link.click();setTimeout(()=>URL.revokeObjectURL(url),10000);
 }catch(error){toast(error.message);}
}
$("#report-pdf").onclick=()=>downloadReport("pdf");
$("#report-source").onclick=()=>downloadReport("zip");
