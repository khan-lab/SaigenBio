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
function samplePath(path) {
    assert.match(path, /^M .+ C /);
    assert.doesNotMatch(path, / [LQ] /);
    const values = path.match(/-?\d+(?:\.\d+)?/g).map(Number);
    let [x, y] = values;
    const samples = [{x, y}];
    for (let i = 2; i < values.length; i += 6) {
        const [ax, ay, bx, by, endX, endY] = values.slice(i, i + 6);
        for (let step = 1; step <= 100; step++) {
            const t = step / 100, u = 1 - t;
            samples.push({
                x: u**3*x + 3*u*u*t*ax + 3*u*t*t*bx + t**3*endX,
                y: u**3*y + 3*u*u*t*ay + 3*u*t*t*by + t**3*endY,
            });
        }
        [x, y] = [endX, endY];
    }
    return samples;
}
const inside = (p, card) => p.x > card.x && p.x < card.x + 192 && p.y > card.y && p.y < card.y + 132;
const route = samplePath(geometry.inputs.find(i=>i.id==="input").d);
assert.ok(route.some(p=>p.y<0));
assert.ok(route.every(p=>!inside(p,fixture.states[1])));
assert.deepEqual(route.at(-1), {x:596,y:66});

// The old bounding-area test would detour around this card even though the
// curve is still well above it while passing its horizontal span.
context.offPath = [state("s", 0, 0), state("target", 900, 400), state("other", 280, 260)];
const clearDirect = evaluate('SaigenGeometry.actionJunction({from:["s","other"],to:"target"}, offPath).inputs[0].d');
assert.equal((clearDirect.match(/ C /g)||[]).length,1);

// The lower side is nearer when both endpoints are below the blocker center.
context.below = [state("s", 0, 55), state("target", 640, 55), state("blocker", 320, 0)];
const lower = samplePath(evaluate('SaigenGeometry.actionJunction({from:["s","blocker"],to:"target"}, below).inputs[0].d'));
assert.ok(lower.some(p=>p.y>132));
assert.ok(lower.every(p=>!inside(p,context.below[2])));
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
const backward = evaluate('actionJunction(flow.actions[0])');
const backwardCards = evaluate('flow.states');
for (const input of backward.inputs) {
    const samples = samplePath(input.d);
    assert.ok(samples.some(p=>p.y<0));
    assert.ok(samples.every(p=>backwardCards.every(card=>!inside(p,card))));
    assert.deepEqual(samples.at(-1), {x:backward.junction.x,y:backward.junction.y});
}
// A single input continues using the existing curve, without a junction.
evaluate('flow.actions[0].from=["qc"];renderEdges()');
assert.equal((edges.innerHTML.match(/data-action=/g)||[]).length,1);
assert.equal((edges.innerHTML.match(/class="edge-junction"/g)||[]).length,0);
console.log("Action junction checks passed: inputs preserved, ancestor detour, one command, and running/planned anchors.");
