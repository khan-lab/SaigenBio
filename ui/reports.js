"use strict";

// Owns report selection, render-job state, polling and download controls.
// Application interaction is supplied through callbacks, not shared globals.
globalThis.SaigenReports = Object.freeze({create({query:$,getFlow,getToken,request,render,hidePopups,clearSelection,toast}){
let reportMode=false,reportSelection=[],reportJob=null,reportRendering=false;
const getState=id=>getFlow().states.find(n=>n.id===id);
function setReportMode(value){
 reportMode=value;clearSelection();
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
  const job=await request("/api/reports",{revision:getFlow().revision,selected:[...reportSelection]});reportJob=job.id;
  await watchReport();
 }catch(error){reportRendering=false;$("#report-status").textContent=error.message;renderReport();}
};
async function watchReport(){
 try{
  const response=await fetch("/api/reports/"+reportJob,{headers:{"X-Saigen-Token":getToken()}});
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
