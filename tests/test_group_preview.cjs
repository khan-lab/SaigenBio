const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const context = vm.createContext({});
for (const name of ["geometry", "analysis-groups", "group-preview"]) {
  vm.runInContext(fs.readFileSync("ui/"+name+".js", "utf8"), context);
}
const {position} = context.SaigenGroupPreview;
const {internalGraph} = context.SaigenAnalysisGroups;
const saved = [
  {id:"shared", x:0, y:4}, {id:"qc", x:300, y:10},
  {id:"model", x:600, y:60}, {id:"report", x:940, y:180},
  {id:"other", x:1240, y:180},
];
const flow = {
  states: saved,
  analysisGroups: [
    {id:"top", stateIds:["qc"]},
    {id:"nested", parentId:"top", stateIds:["model"]},
    {id:"leaf", parentId:"nested", stateIds:["report"]},
  ],
  actions: [
    {id:"qc", from:["shared"], to:"qc"},
    {id:"model", from:["qc", "shared"], to:"model"},
    {id:"report", from:["model", "qc"], to:"report"},
    {id:"other", from:["report"], to:"other"},
  ],
};
const top = internalGraph(flow,"top");
assert.deepEqual(top.nodes, saved.slice(1,4));
assert.deepEqual(Array.from(top.actions, a=>[a.id,a.from.join(",")]), [["model","qc"],["report","model,qc"]]);
assert.deepEqual(flow.actions[1].from, ["qc","shared"]);
assert.equal(internalGraph(flow,"leaf").actions.length, 0);
assert.equal(internalGraph(flow,"unknown").nodes.length, 0);

assert.equal(position({left:50,right:190,top:200,bottom:270},560,360,1200,800).x,198);
assert.equal(position({left:1000,right:1140,top:600,bottom:670},560,360,1200,800).x,432);
const narrow = position({left:100,right:300,top:420,bottom:540},366,310,390,600);
assert.equal(narrow.x,12);
assert.ok(narrow.y+310<=420);
const short = position({left:100,right:300,top:100,bottom:200},296,290,320,310);
assert.ok(short.y>=12 && short.y+short.maxHeight<=298);
console.log("Group previews retain nested member positions, internal branches and viewport bounds.");
