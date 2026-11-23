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
assert.match(card(overview.summaries[0],escape),/aria-label="Expand HeLa &lt;cells&gt;, 2 results, 1 running result · 1 failed result"/);
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
const figureView=()=>project(figureFlow,{automatic:new Map(),overrides:new Map(),full:false,scale:.35,
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
const cycleOptions={automatic:new Map(),overrides:new Map(),full:false,scale:.48,
  figureFor:node=>node.id==="b"?{id:"wide"}:null};
const cycleView=project(cycleFlow,cycleOptions);
const {arrange}=globalThis.SaigenAnalysisGroups;
const overviewLayout=arrange(cycleView,.48);
assert.deepEqual(arrange(cycleView,.48),overviewLayout);
assert.equal(cycleView.connections.filter(edge=>edge.links.some(link=>
  ["other_to_inner","middle_to_other"].includes(link.action.id))).length,2);
const overviewKey=overviewLayout.cards.map(card=>card.id).sort().join("|");
const savedFlow={...cycleFlow,overviewLayouts:{[overviewKey]:overviewLayout}};
const savedView=project(savedFlow,cycleOptions);
assert.deepEqual(savedView.placed.map(({id,x,y})=>({id,x,y})).sort((a,b)=>a.id.localeCompare(b.id)),
  overviewLayout.cards.slice().sort((a,b)=>a.id.localeCompare(b.id)));
const smaller=project(savedFlow,{...cycleOptions,scale:.22});
for(const [i,a] of smaller.placed.entries())for(const b of smaller.placed.slice(i+1)){
  assert.ok(a.x+(a.width??192)<=b.x||b.x+(b.width??192)<=a.x||
            a.y+(a.height??132)<=b.y||b.y+(b.height??132)<=a.y,"zoomed-out cards must clear one another");
}
assert.deepEqual(project(savedFlow,{...cycleOptions,full:true}).states,states);

const {closeInspections}=globalThis.SaigenAnalysisGroups;
const inspections=new Map([["large",false],["middle",false],["inner",false]]);
assert.equal(closeInspections(low.groups,inspections,.9),false);
assert.equal(closeInspections(low.groups,inspections,.7),true);
assert.deepEqual([...inspections.keys()],["large"],"deeper inspections expire at higher zoom levels");
assert.equal(closeInspections(low.groups,inspections,.55),true);
assert.equal(inspections.size,0);

// Keep failure emphasis independent of the running count, including when
// the two counts originate in different descendants of a collapsed group.
for(const [running,failed] of [[0,0],[2,0],[0,1],[2,1]]){
  const markup=card({...low.summaries[0],running,failed},escape);
  assert.equal(markup.includes('class="group-card-running">2 running results'),running>0);
  assert.equal(markup.includes('class="group-card-failed">1 failed result'),failed>0);
  assert.equal(markup.includes('class="group-card-status"'),running+failed>0);
}
