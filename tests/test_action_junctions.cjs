const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
const app=fs.readFileSync("ui/app.js","utf8");
const edges={innerHTML:""};
const context=vm.createContext({document:{querySelector:s=>{assert.equal(s,"#edges");return edges;}}});
for(const file of ["geometry.js","paths.js","api.js","workflows.js"])vm.runInContext(fs.readFileSync("ui/"+file,"utf8"),context);
vm.runInContext(app.slice(0,app.indexOf("function render(){")),context);
const evaluate=code=>vm.runInContext(code,context);
const state=(id,x,y,status="completed")=>({id,title:id,x,y,status,files:[],artifactIds:[],manifest:[]});
const action={id:"normalize",from:["qc","input"],to:"normalized",label:"seurat_workflow.R",status:"completed",inputArtifacts:[]};
const fixture={states:[state("input",0,0),state("qc",320,0),state("normalized",640,0)],actions:[action],artifacts:{}};
context.fixture=fixture;
evaluate("flow=JSON.parse(JSON.stringify(fixture))");
const before=evaluate("JSON.stringify(flow)");
const geometry=evaluate("actionJunction(flow.actions[0])");
assert.equal(geometry.inputs.length,2);
assert.deepEqual(Array.from(geometry.inputs,i=>i.id),["qc","input"]);
assert.equal(geometry.junction.x,596);
assert.equal(geometry.junction.y,66);
assert.equal(geometry.output,"M 596 66 L 640 66");
// The ancestor route must clear the QC card, rather than passing behind it.
const route=geometry.inputs.find(i=>i.id==="input").points;
assert.ok(route.some(p=>p.y<0));
for(let i=1;i<route.length;i++){
    const a=route[i-1],b=route[i];
    if(a.y===b.y&&a.y>=0&&a.y<=132)
        assert.ok(Math.max(a.x,b.x)<=320||Math.min(a.x,b.x)>=512);
    if(a.x===b.x&&a.x>=320&&a.x<=512)
        assert.ok(Math.max(a.y,b.y)<=0||Math.min(a.y,b.y)>=132);
}
evaluate("renderEdges()");
assert.equal((edges.innerHTML.match(/data-action=/g)||[]).length,1);
assert.equal((edges.innerHTML.match(/class="edge-label"/g)||[]).length,1);
assert.equal((edges.innerHTML.match(/marker-end=/g)||[]).length,1);
assert.equal((edges.innerHTML.match(/class="edge-junction"/g)||[]).length,1);
assert.ok(edges.innerHTML.includes("qc + input"));
assert.equal(evaluate("JSON.stringify(flow)"),before);

// Running/planned results attach at their card edges and keep one outgoing action.
for(const status of ["running","planned"]){
    context.status=status;
    evaluate('flow.states[2].status=status;flow.actions[0].status=status;renderEdges()');
    const g=evaluate("actionJunction(flow.actions[0])");
    assert.equal(g.junction.y,66);
    assert.ok(g.output.endsWith("L 640 66"));
    assert.equal((edges.innerHTML.match(/class="edge-label"/g)||[]).length,1);
    assert.equal((edges.innerHTML.match(/<animateMotion/g)||[]).length,status==="running"?1:0);
}

// Independent sources remain separate paths into the same junction after dragging.
evaluate('flow.states[0].y=240;flow.states[2].y=120;renderEdges()');
assert.equal(evaluate("actionJunction(flow.actions[0]).inputs.length"),2);
assert.equal(evaluate("actionJunction(flow.actions[0]).junction.y"),186);
// A target dragged to the left must route above its source cards too.
evaluate('flow.states[2].x=-320;flow.states[2].y=0');
assert.ok(evaluate('actionJunction(flow.actions[0]).inputs.every(i=>i.points&&i.points.some(p=>p.y<0))'));
// A single input continues using the existing curve, without a junction.
evaluate('flow.actions[0].from=["qc"];renderEdges()');
assert.equal((edges.innerHTML.match(/data-action=/g)||[]).length,1);
assert.equal((edges.innerHTML.match(/class="edge-junction"/g)||[]).length,0);
console.log("Action junction checks passed: inputs preserved, ancestor detour, one command, and running/planned anchors.");
