const assert=require("node:assert/strict");
require("../ui/geometry.js");
require("../ui/analysis-groups.js");
const {project,edge,card,dependencyList,memberIds,path,translate}=globalThis.SaigenAnalysisGroups;

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
const view=(scale=.3,full=false)=>project(flow,{full,scale});
const escape=s=>s.replaceAll("<","&lt;").replaceAll(">","&gt;");

const overview=view();
assert.deepEqual(overview.states.map(state=>state.id),["input","compare"]);
assert.deepEqual(overview.actions.map(action=>action.id),[]);
assert.deepEqual(overview.summaries.map(group=>[group.count,group.running,group.failed]),[[2,1,1],[1,0,0]]);
assert.ok(overview.summaries.every(group=>group.width*.3>=112));
assert.match(card(overview.summaries[0],escape),/aria-label="Show nodes in HeLa &lt;cells&gt;, 2 results, 1 running result · 1 failed result"/);
const compare=overview.connections.find(link=>link.from.id==="group:hela"&&link.to.id==="compare");
assert.deepEqual(compare.links.map(link=>[link.action.id,link.source.id]),[
 ["compare_cells","a"],["compare_cells","b"],["compare_counts","a"],
]);
assert.equal(overview.connections.flatMap(link=>link.links).some(link=>link.action.id==="markers"),false);
assert.match(edge(compare,0,escape),/3 dependencies from HeLa &lt;cells&gt; to Compare/);
assert.match(dependencyList(compare,escape),/Cell counts \+ Cell markers → Compare/);
assert.match(dependencyList(compare,escape),/data-group-target="compare"/);

assert.deepEqual(view(1).summaries.map(group=>group.groupId),["hela","other"]);
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
const nestedView=(scale,full=false)=>project(nested,{full,scale});
const low=nestedView(.35);
assert.deepEqual(low.summaries.map(group=>group.groupId),["large","other"]);
assert.deepEqual([low.summaries[0].count,low.summaries[0].running,low.summaries[0].failed],[2,1,1]);
assert.equal(low.endpoint.get("b"),"group:large");
for(const scale of [.22,.86,1.8]){
 const groups=nestedView(scale);
 assert.deepEqual(groups.summaries.map(group=>group.groupId),["large","other"]);
 const outer=groups.summaries[0];
 assert.equal(outer.x+outer.width/2,(610+1220+192)/2,"group center follows the full descendant bounds");
 assert.equal(outer.y+outer.height/2,66);
 assert.deepEqual(nestedView(scale,true).states,states);
}
assert.deepEqual(path(nested.analysisGroups,"b").map(group=>group.id),["large","middle","inner"]);
assert.deepEqual([...memberIds(nested.analysisGroups,"middle")],["a","b"]);
assert.deepEqual([...memberIds(nested.analysisGroups,"inner")],["b"]);
assert.deepEqual(translate(low,[{id:"group:large",dx:20,dy:-40}]),[
 {op:"edit_state",id:"a",changes:{x:630,y:-40}},
 {op:"edit_state",id:"b",changes:{x:1240,y:-40}},
]);
assert.deepEqual(translate(low,[{id:"input",dx:40,dy:0}]),[
 {op:"edit_state",id:"input",changes:{x:40,y:0}},
]);
assert.equal(JSON.stringify(flow),before);
console.log("Analysis group projection, shared coordinates, deep paths, and edge traceability passed.");

const figures = {
  a: {id:"plot_a"},
  b: {id:"plot_b"},
  other: {id:"plot_other"},
  compare: {id:"unrelated"},
};
const figureFlow={...nested,states:states.map(node=>({
  ...node,
  status: node.id==="input"?"failed":"completed",
  finishedAt: node.id==="a"?"2026-01-01":"2026-02-01",
}))};
const figureView=()=>project(figureFlow,{full:false,scale:.35,
  figureFor:node=>figures[node.id]});
let summary=figureView().summaries[0];
assert.equal(summary.figure.node.id,"b","the outer group uses the latest figure from a nested result");
assert.match(card(summary,escape,node=>'<img src="'+node.id+'">'), /figure from Cell markers/);
delete figures.b;
assert.equal(figureView().summaries[0].figure.node.id,"a","an unavailable figure can fall back to another result");
delete figures.a;
summary=figureView().summaries[0];
assert.equal(summary.figure,null,"groups without available member figures stay text-only");
assert.doesNotMatch(card(summary,escape,()=>{throw Error("no figure expected");}), /group-card-thumbnail/);

const cycleFlow={...nested,actions:[...actions,
  {id:"other_to_inner",from:["other"],to:"b"},
  {id:"middle_to_other",from:["a"],to:"other"},
]};
const cycleOptions={full:false,scale:.48,
  figureFor:node=>node.id==="b"?{id:"wide"}:null};
const cycleView=project(cycleFlow,cycleOptions);
const {arrange}=globalThis.SaigenAnalysisGroups;
const overviewLayout=arrange(cycleView,.48);
assert.deepEqual(arrange(cycleView,.48),overviewLayout);
assert.equal(cycleView.connections.filter(edge=>edge.links.some(link=>
  ["other_to_inner","middle_to_other"].includes(link.action.id))).length,2);
const overviewKey=overviewLayout.cards.map(card=>card.id).sort().join("|");
const savedFlow={...cycleFlow,overviewLayouts:{[overviewKey]:overviewLayout}};
assert.deepEqual(project(savedFlow,cycleOptions).placed,cycleView.placed,"old separate layout does not displace the current group centers");
assert.deepEqual(project(savedFlow,{...cycleOptions,full:true}).states,states);

// Keep failure emphasis independent of the running count, including when
// the two counts originate in different descendants of a collapsed group.
for(const [running,failed] of [[0,0],[2,0],[0,1],[2,1]]){
  const markup=card({...low.summaries[0],running,failed},escape);
  assert.equal(markup.includes('class="group-card-running">2 running results'),running>0);
  assert.equal(markup.includes('class="group-card-failed">1 failed result'),failed>0);
  assert.equal(markup.includes('class="group-card-status"'),running+failed>0);
}
