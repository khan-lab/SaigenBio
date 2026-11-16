const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm');
const elements=new Map();
const query=id=>{if(!elements.has(id))elements.set(id,{hidden:false,textContent:'',classList:{remove(){},toggle(){}},setAttribute(){}});return elements.get(id);};
const context=vm.createContext({location:{hash:''},fetch:async()=>({ok:true,json:async()=>({status:'ready',revision:3,warnings:[]})})});
vm.runInContext(fs.readFileSync('ui/reports.js','utf8'),context);
let flow={revision:3,states:[{id:'a'},{id:'b'}]},submitted;
const reports=context.SaigenReports.create({query,getFlow:()=>flow,getToken:()=>'',request:async(path,body)=>{submitted=body;return {id:'report1'};},render(){reports.render();},hidePopups(){},clearSelection(){},toast(){}});
(async()=>{
 reports.setMode(true);reports.toggleState('b');reports.toggleState('a');
 assert.equal(reports.position('b'),0);assert.equal(reports.position('a'),1);
 await query('#report-create').onclick();
 assert.equal(submitted.revision,3);assert.deepEqual(Array.from(submitted.selected),['b','a']);
 assert.equal(query('#report-pdf').hidden,false);
 reports.toggleState('b');assert.equal(query('#report-pdf').hidden,true);
 flow={...flow,states:[]};reports.render();assert.equal(query('#report-create').disabled,true);
 reports.setMode(false);assert.equal(reports.active,false);assert.equal(reports.position('a'),-1);
 console.log('Report UI checks passed: ordered selection, snapshot revision, completion, invalidation and exit.');
})().catch(error=>{console.error(error);process.exitCode=1;});
