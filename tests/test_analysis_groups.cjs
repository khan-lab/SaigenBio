const assert=require("node:assert/strict");
require("../ui/geometry.js");
require("../ui/analysis-groups.js");
const {compactAt,project,edge,card,dependencyList}=globalThis.SaigenAnalysisGroups;

const states=[
 {id:"input",title:"Shared input",x:0,y:0,status:"imported"},
 {id:"a",title:"Cell counts",x:610,y:0,status:"running"},
 {id:"b",title:"Cell markers",x:1220,y:0,status:"failed"},
 {id:"other",title:"Other cells",x:610,y:440,status:"completed"},
 {id:"compare",title:"Compare",x:1830,y:0,status:"planned"},
];
const actions=[
 {id:"counts",label:"Quantify",from:["input"],to:"a",status:"running"},
 {id:"markers",label:"Find markers",from:["a"],to:"b",status:"failed"},
 {id:"compare_cells",label:"Compare cells",from:["a","b","other"],to:"compare",status:"planned"},
 {id:"compare_counts",label:"Compare counts",from:["a"],to:"compare",status:"planned"},
 {id:"compare_input",label:"Compare input",from:["input","other"],to:"compare",status:"planned"},
];
const flow={states,actions,analysisGroups:[
 {id:"hela",title:"HeLa <cells>",stateIds:["a","b"]},
 {id:"other",title:"Other cells",stateIds:["other"]},
]};
const before=JSON.stringify(flow);
const overrides=new Map(),automatic=new Map();
const view=(scale=.3,full=false)=>project(flow,{automatic,overrides,full,scale});
const escape=s=>s.replaceAll("<","&lt;").replaceAll(">","&gt;");

assert.equal(compactAt(.55,false),true);
assert.equal(compactAt(.59,true),true);
assert.equal(compactAt(.59,false),false);
assert.equal(compactAt(.65,true),false);
const overview=view();
assert.deepEqual(overview.states.map(state=>state.id),["input","compare"]);
assert.deepEqual(overview.actions.map(action=>action.id),[]);
assert.deepEqual(overview.summaries.map(group=>[group.count,group.running,group.failed]),[[2,1,1],[1,0,0]]);
assert.ok(overview.summaries.every(group=>group.width*.3>=112));
assert.match(card(overview.summaries[0],escape),/HeLa &lt;cells&gt;.*1 running result · 1 failed result/);
const compare=overview.connections.find(link=>link.from.id==="group:hela"&&link.to.id==="compare");
assert.deepEqual(compare.links.map(link=>[link.action.id,link.source.id]),[
 ["compare_cells","a"],["compare_cells","b"],["compare_counts","a"],
]);
assert.equal(overview.connections.flatMap(link=>link.links).some(link=>link.action.id==="markers"),false);
assert.match(edge(compare,0,escape),/3 dependencies from HeLa &lt;cells&gt; to Compare/);
assert.match(dependencyList(compare,escape),/Cell counts \+ Cell markers → Compare/);
assert.match(dependencyList(compare,escape),/data-group-target="compare"/);

overrides.set("hela",false);
assert.deepEqual(view().states.map(node=>node.id),["input","a","b","compare"]);
assert.equal(view().actions.some(action=>action.id==="markers"),true);
overrides.set("other",true);
assert.deepEqual(view(1).summaries.map(group=>group.groupId),["other"]);
assert.deepEqual(view(1,true).states,states);
assert.deepEqual(view(1,true).actions,actions);
assert.equal(view(1,true).connections.length,0);
assert.equal(JSON.stringify(flow),before);
const nested={...flow,analysisGroups:[
 {id:"large",title:"Cell type",stateIds:[]},
 {id:"middle",parentId:"large",title:"Intermediate",stateIds:["a"]},
 {id:"inner",parentId:"middle",title:"Specific method",stateIds:["b"]},
 flow.analysisGroups[1],
]};
const nestedView=(scale,automatic=new Map(),overrides=new Map())=>project(nested,{automatic,overrides,full:false,scale});
const hierarchyZoom=new Map();
const low=nestedView(.35,hierarchyZoom);
assert.deepEqual(low.summaries.map(group=>group.groupId),["large","other"]);
assert.deepEqual([low.summaries[0].count,low.summaries[0].running,low.summaries[0].failed],[2,1,1]);
assert.equal(low.endpoint.get("b"),"group:large");
const middle=nestedView(.7,hierarchyZoom);
assert.deepEqual(middle.summaries.map(group=>group.groupId),["middle"]);
assert.equal(middle.endpoint.get("b"),"group:middle");
const deep=nestedView(.86,hierarchyZoom);
assert.deepEqual(deep.summaries.map(group=>group.groupId),["inner"]);
assert.equal(deep.endpoint.has("a"),false);
assert.equal(nestedView(1,hierarchyZoom).summaries.length,0);
const opened=nestedView(.35,new Map(),new Map([["large",false]]));
assert.deepEqual(opened.summaries.map(group=>group.groupId),["middle","other"]);
assert.match(card(opened.summaries[0],escape),/Cell type.*Intermediate/);
console.log("Analysis group projection, edge traceability, zoom, overrides and report isolation passed.");
