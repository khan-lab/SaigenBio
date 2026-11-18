const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
const app=fs.readFileSync("ui/app.js","utf8");
const context=vm.createContext({});
for(const file of ["geometry.js","paths.js","api.js","workflows.js"])vm.runInContext(fs.readFileSync("ui/"+file,"utf8"),context);
vm.runInContext(app.slice(0,app.indexOf("function render(){")),context);
const evaluate=code=>vm.runInContext(code,context);
const statuses=["planned","running","completed","imported","failed","cancelled","unknown","saved"];
for(const fromStatus of statuses)for(const toStatus of statuses){
    context.source={id:"source",x:0,y:80,status:fromStatus};
    context.target={id:"target",x:320,y:80,status:toStatus};
    assert.equal(evaluate("edgePath(source,target).d"),"M 192 146 L 320 146");
    assert.equal(evaluate("edgeAnchor(target).x"),320);
    assert.equal(evaluate("edgeAnchor(target).y"),146);
}
context.target.y=260;
assert.ok(evaluate("edgePath(source,target).d").includes(" C "));
assert.ok(evaluate("edgePath(source,target).d").endsWith("320 326"));
for(const status of ["planned","running"]){
    context.node={title:"Normalized marker maps",status,note:"Full explanation",expectedSummary:"Expected result sentence."};
    const before=JSON.stringify(context.node),html=evaluate("nodeContent(node)");
    assert.ok(html.includes("Normalized marker maps"));
    assert.ok(html.includes(status==="running"?"Running":"Planned"));
    assert.ok(!html.includes("Full explanation"));
    assert.ok(!html.includes("Expected result sentence."));
    assert.ok(!html.includes('class="ring"'));
    assert.equal(JSON.stringify(context.node),before);
}
console.log("Node geometry checks passed: stable anchors across statuses, straight aligned edges, and concise pending cards.");

const align = evaluate("SaigenGeometry.alignment");
const above = {id:"above", x:100, y:0, status:"planned"};
const beside = {id:"beside", x:400, y:200, status:"completed"};
const moving = {id:"moving", x:104, y:196};
const both = align(moving, [moving, above, beside], 1);
assert.equal(both.x, 100);
assert.equal(both.y, 200);
assert.equal(both.guides.x.at, 196);
assert.equal(both.guides.y.at, 266);
assert.equal(both.guides.x.end, 340);
assert.equal(both.guides.y.start, 92);
assert.equal(align(moving, [above, beside], 2).x, moving.x);
assert.equal(align({...moving,x:110}, [above], .5).x, 100);
assert.equal(align(moving, [{...above,y:-800}], 1).x, moving.x);
assert.equal(align(moving, [above], 1, both.guides, true).x, moving.x);

const competitor = {...above,id:"closer",x:108};
const nearCompetitor = {...moving,x:107};
assert.equal(align(nearCompetitor, [above, competitor], 1).x, 108);
assert.equal(align(nearCompetitor, [competitor, above], 1, both.guides).x, 100);
assert.equal(align({...moving,x:110}, [above, competitor], 1, both.guides).x, 108);
assert.equal(align(moving, [competitor, above], 1).guides.x.id, "above");
console.log("Alignment checks passed: matching axes, zoom, range, tie-breaking, retention and bypass.");
