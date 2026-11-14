const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
const app=fs.readFileSync("ui/app.js","utf8");
const context=vm.createContext({});
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
