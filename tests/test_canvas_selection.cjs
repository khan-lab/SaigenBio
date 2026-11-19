const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const elements=new Map(),cards=new Map(),listeners=new Map(),timeouts=[];
const classes=()=>{const values=new Set();return {add:v=>values.add(v),remove:v=>values.delete(v),contains:v=>values.has(v),toggle(v,on){const yes=on===undefined?!values.has(v):on;if(yes)values.add(v);else values.delete(v);return yes;}};};
function element(selector){
 if(!elements.has(selector))elements.set(selector,{
   hidden:false,open:false,disabled:false,textContent:'',innerHTML:'',style:{},dataset:{},classList:classes(),offsetWidth:230,attributes:{},
   setAttribute(k,v){this.attributes[k]=v;},getBoundingClientRect(){return {left:0,top:76,width:1000,height:650,right:1000,bottom:726};},
   addEventListener(type,fn){listeners.set(selector+':'+type,fn);},
   querySelector(s){const match=s.match(/data-state="([^"]+)"/);return match?cards.get(match[1]):element(selector+' '+s);},
   querySelectorAll(s){return s==='[data-state]'?[...cards.values()]:[];},
   setPointerCapture(id){this.capture=id;},hasPointerCapture(id){return this.capture===id;},releasePointerCapture(){this.capture=null;},
   close(){this.open=false;},showModal(){this.open=true;},focus(){},
 });
 return elements.get(selector);
}
const doc={querySelector:s=>s==='dialog[open]'?null:element(s),addEventListener:(type,fn)=>listeners.set('document:'+type,fn)};
const fixture={project:'Selection test',revision:0,states:['a','b','c'].map((id,i)=>({id,title:id,x:i*320,y:100,status:'planned',origin:'manual',files:[],artifactIds:[],manifest:[]})),actions:[],artifacts:{}};
let server=structuredClone(fixture),failure=null,submissions=[];
const response=(value,ok=true,status=200)=>({ok,status,json:async()=>structuredClone(value)});
const context=vm.createContext({document:doc,innerWidth:1280,innerHeight:800,CSS:{escape:v=>v},
 window:{addEventListener:(type,fn)=>listeners.set('window:'+type,fn)},location:{hash:''},
 clearTimeout(){},setTimeout(fn){timeouts.push(fn);},
 fetch:async(path,init)=>{
   if(path==='/api/history')return response([]);
   if(path==='/api/flow')return response(server);
   assert.equal(path,'/api/edit');const payload=JSON.parse(init.body);submissions.push(payload);
   if(failure==='offline')throw new Error('Offline');
   if(failure==='stale'){server.states[0].x=999;server.revision++;return response({error:'Project changed'},false,409);}
   assert.equal(payload.revision,server.revision);
   for(const op of payload.operations){assert.equal(op.op,'edit_state');assert.deepEqual(Object.keys(op.changes).sort(),['x','y']);}
   for(const op of payload.operations)Object.assign(server.states.find(n=>n.id===op.id),op.changes);
   server.revision++;return response(server);
 }});
for(const name of ['geometry.js','paths.js','api.js','workflows.js','reports.js','explanation-editor.js','detail-controller.js'])vm.runInContext(fs.readFileSync('ui/'+name,'utf8'),context);
const app=fs.readFileSync('ui/app.js','utf8'),evaluate=code=>vm.runInContext(code,context);
evaluate(app.slice(0,app.indexOf('$("#editor-form").onsubmit')));
evaluate('render=()=>syncSelection();renderEdges=()=>{};renderWorkflowLabels=()=>{};hidePopups=()=>{};showPreview=()=>{};');
evaluate(app.slice(app.indexOf('$("#nodes").addEventListener("keydown"'),app.indexOf('$("#nodes").addEventListener("pointerout"')));
evaluate(app.slice(app.indexOf('let suppressClick=false;'),app.indexOf('window.addEventListener("hashchange",route);')));
evaluate(app.slice(app.indexOf('reports=SaigenReports.create'),app.indexOf('render();start();setInterval(poll,1000);')));
context.fixture=fixture;evaluate('flow=copy(fixture);ready=true;camera={x:0,y:0,scale:.5};');
element('#detail-view').hidden=true;
for(const node of fixture.states){
 const card=element('card:'+node.id);card.dataset.state=node.id;
 card.closest=s=>s==='[data-state]'?card:null;card.contains=()=>false;cards.set(node.id,card);
}
const event=(target,extra={})=>({target,button:0,pointerId:1,clientX:10,clientY:20,shiftKey:false,altKey:true,preventDefault(){this.prevented=true;},...extra});
const call=(selector,type,e)=>listeners.get(selector+':'+type)(e);
const selected=()=>Array.from(evaluate('[...selection]')).sort();
const positions=()=>JSON.parse(evaluate('JSON.stringify(flow.states.map(({id,x,y})=>({id,x,y})))'));
const flush=()=>{while(timeouts.length)timeouts.shift()();};
async function click(id,shift=false){
 const e=event(cards.get(id),{shiftKey:shift});
 call('#viewport','pointerdown',e);await call('#viewport','pointerup',e);
 // Pointer capture retargets an ordinary click to the viewport: selection must
 // already be applied by pointerup. Shift gestures retain native node clicks.
 if(shift)call('#nodes','click',e);
 else assert.deepEqual(selected(),[id]);
 flush();
}
async function drag(id,dx,dy){
 const card=cards.get(id);call('#viewport','pointerdown',event(card));
 call('#viewport','pointermove',event(card,{clientX:10+dx,clientY:20+dy}));
 await call('#viewport','pointerup',event(card,{clientX:10+dx,clientY:20+dy}));
 call('#nodes','click',event(card));flush();
}
(async()=>{
 await click('a');assert.deepEqual(selected(),['a']);
 await click('b',true);assert.deepEqual(selected(),['a','b']);
 assert.equal(cards.get('b').attributes['aria-pressed'],'true');
 assert.equal(element('#selection-count').textContent,'2 nodes selected');
 assert.equal(element('#single-selection-actions').hidden,true);
 await click('a',true);assert.deepEqual(selected(),['b']);
 assert.equal(element('#single-selection-actions').hidden,false);
 await click('a',true);
 const before=positions();
 await drag('a',30,20);
 assert.deepEqual(selected(),['a','b'],'drag-generated click must not collapse the group');
 assert.deepEqual(positions(),before.map(n=>n.id==='c'?n:{...n,x:n.x+60,y:n.y+40}));
 assert.equal(submissions.length,1);assert.equal(submissions[0].operations.length,2);
 assert.equal(server.revision,1,'one group move is one revision');
 assert.equal(element('#undo').disabled,true); // Fake history is intentionally empty.
 await click('b');assert.deepEqual(selected(),['b'],'plain click collapses to one node');
 await click('a',true);
 const beforeCancel=positions();
 call('#viewport','pointerdown',event(cards.get('a')));
 call('#viewport','pointermove',event(cards.get('a'),{clientX:100,clientY:100}));
 call('#viewport','pointercancel',event(cards.get('a')));flush();
 assert.deepEqual(positions(),beforeCancel);assert.equal(submissions.length,1);
 // A network failure restores the whole group. A stale response keeps the server's positions.
 failure='offline';await drag('a',40,30);assert.deepEqual(positions(),beforeCancel);
 failure='stale';await drag('a',40,30);
 assert.equal(positions()[0].x,999);assert.equal(positions()[1].x,server.states[1].x);
 failure=null;
 call('#nodes','keydown',event(cards.get('c'),{key:' ',shiftKey:true}));
 assert.deepEqual(selected(),['a','b','c']);
 call('#nodes','keydown',event(cards.get('c'),{key:' ',shiftKey:true}));
 assert.deepEqual(selected(),['a','b']);
 call('document','keydown',event(cards.get('a'),{key:'Escape'}));assert.deepEqual(selected(),[]);
 await click('a');await click('b',true);
 const background={closest:()=>null};call('#viewport','pointerdown',event(background));
 await call('#viewport','pointerup',event(background));assert.deepEqual(selected(),[]);
 // Shift gestures never start a layout drag, even if the pointer moves.
 const count=submissions.length;
 call('#viewport','pointerdown',event(cards.get('a'),{shiftKey:true}));
 call('#viewport','pointermove',event(cards.get('a'),{clientX:100,shiftKey:true}));
 await call('#viewport','pointerup',event(cards.get('a'),{clientX:100,shiftKey:true}));
 assert.equal(submissions.length,count);
 // Report order and normal selection remain independent, including Shift-clicks.
 await click('a');await click('b',true);evaluate('reports.setMode(true)');
 assert.deepEqual(selected(),[]);
 await click('b',true);await click('a',true);
 assert.equal(evaluate('reports.position("b")'),0);assert.equal(evaluate('reports.position("a")'),1);
 assert.deepEqual(selected(),[]);
 evaluate('reports.setMode(false)');assert.equal(evaluate('reports.position("a")'),-1);
 // Updates prune disappeared nodes and hide the toolbar if nothing remains.
 await click('a');evaluate('flow.states=flow.states.filter(n=>n.id!=="a");syncSelection()');
 assert.deepEqual(selected(),[]);assert.equal(element('#selection-tools').hidden,true);
 console.log('Canvas selection checks passed: toggling, group save, cancellation, failure/stale recovery, keyboard, report isolation and pruning.');
})().catch(error=>{console.error(error);process.exitCode=1;});
