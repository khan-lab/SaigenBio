"use strict";

// Owns report selection and a frozen contents-preview -> render -> download lifecycle.
globalThis.SaigenReports = Object.freeze({create({query:$,getFlow,getToken,request,render,hidePopups,clearSelection,toast}){
let reportMode=false,reportSelection=[],reportJob=null,reportRendering=false,reportPreview=null;
const getState=id=>getFlow().states.find(n=>n.id===id);
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function setReportMode(value){
 if(reportRendering)return;
 reportMode=value;clearSelection();
 $("#viewport").classList.remove("connecting");
 $("#viewport").classList.toggle("editing",!value);
 $("#edit-tools").hidden=value;
 if(value)location.hash="";else{reportSelection=[];invalidateReport();}
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
 reportJob=null;reportPreview=null;$("#report-status").textContent="";
 $("#report-pdf").hidden=true;$("#report-source").hidden=true;
 $("#report-preview").close();
}
function renderReport(){
 if(!reportRendering&&!reportPreview){
  const active=reportSelection.filter(id=>getState(id));
  if(active.length!==reportSelection.length)invalidateReport();
  reportSelection=active;
 }
 $("#report-tools").hidden=!reportMode;
 $("#report-count").textContent=reportSelection.length?reportSelection.length+(reportSelection.length===1?" state":" states")+" · click to add or remove":"Select states in report order";
 $("#report-create").disabled=!reportSelection.length||reportRendering;
 for(const id of ["#report-clear","#report-template","#report-cancel","#report-toggle"])$(id).disabled=reportRendering;
 $("#report-toggle").disabled=reportRendering||!getToken();
}
$("#report-toggle").onclick=()=>setReportMode(!reportMode);
$("#report-cancel").onclick=()=>setReportMode(false);
$("#report-clear").onclick=()=>{invalidateReport();reportSelection=[];render();};
$("#report-template").onchange=()=>{invalidateReport();renderReport();};
$("#report-preview-close").onclick=()=>$("#report-preview").close();
$("#report-create").onclick=async()=>{
 reportRendering=true;reportJob=null;reportPreview=null;renderReport();
 $("#report-pdf").hidden=true;$("#report-source").hidden=true;
 $("#report-status").textContent="Preparing contents preview…";
 try{
  const preview=await request("/api/reports/preview",{revision:getFlow().revision,selected:[...reportSelection],template:$("#report-template").value});
  reportPreview=preview;reportJob=preview.id;
  $("#report-preview-body").innerHTML='<p><strong>'+esc(preview.template.name)+'</strong> · Revision '+esc(preview.revision)+'</p><p>'+esc(preview.template.description)+'</p><p class="report-preview-hint">Contents outline, not a rendered PDF. Export uses this frozen snapshot, even if the canvas changes.</p><ol>'+preview.outline.map(n=>'<li><h3>'+esc(n.title)+'</h3><span class="preview-label">'+esc(n.status)+'</span><ul>'+n.sections.map(s=>'<li>'+esc(s)+'</li>').join('')+'</ul></li>').join('')+'</ol>'+(preview.warnings.length?'<h3>Evidence warnings</h3><ul>'+preview.warnings.map(w=>'<li>'+esc(w)+'</li>').join('')+'</ul>':'')+'<p>Analysis execution stays disabled. The bundle retains the selected snapshot and provenance manifest.</p>';
  $("#report-preview").showModal();$("#report-status").textContent="Contents prepared · revision "+preview.revision;
 }catch(error){$("#report-status").textContent=error.message;}
 finally{reportRendering=false;renderReport();}
};
$("#report-export").onclick=async()=>{
 if(!reportPreview||reportRendering)return;
 const preview=reportPreview;
 reportRendering=true;renderReport();$("#report-preview").close();
 $("#report-status").textContent="Preparing PDF…";
 try{
  const job=await request("/api/reports/"+preview.id+"/render",{revision:preview.revision});
  reportJob=job.id;await watchReport(job.id);
 }catch(error){reportRendering=false;$("#report-status").textContent=error.message;renderReport();}
};
async function watchReport(ident){
 try{
  const response=await fetch("/api/reports/"+ident,{headers:{"X-Saigen-Token":getToken()}});
  const job=await response.json();if(!response.ok)throw new Error(job.error);
  if(ident!==reportJob)return;
  if(job.status==="ready"){
   reportRendering=false;$("#report-status").textContent="Ready · revision "+job.revision+(job.warnings.length?" · "+job.warnings.length+" evidence warning(s)":"");
   $("#report-pdf").hidden=false;$("#report-source").hidden=false;renderReport();return;
  }
  if(job.status==="failed")throw new Error(job.error);
  $("#report-status").textContent="Rendering PDF…";setTimeout(()=>watchReport(ident),1000);
 }catch(error){reportRendering=false;$("#report-status").textContent=error.message;renderReport();}
}
async function downloadReport(kind){
 try{
  const response=await fetch("/api/reports/"+reportJob+"/"+kind,{headers:{"X-Saigen-Token":getToken()}});
  if(!response.ok)throw new Error((await response.json()).error);
  const url=URL.createObjectURL(await response.blob()),link=document.createElement("a");
  link.href=url;link.download="saigen-report."+kind;link.click();setTimeout(()=>URL.revokeObjectURL(url),10000);
 }catch(error){toast(error.message);}
}
$("#report-pdf").onclick=()=>downloadReport("pdf");
$("#report-source").onclick=()=>downloadReport("zip");
return Object.freeze({get active(){return reportMode;},position:id=>reportSelection.indexOf(id),
 setMode:setReportMode,toggleState:toggleReportState,render:renderReport});
}});
