"use strict";

// Pure canvas geometry. Inputs are recorded states; no DOM or application state.
globalThis.SaigenGeometry = (() => {
const W=192,H=132;
function edgeAnchor(n,right=false){return {x:n.x+(right?W:0),y:n.y+H/2};}
function edgePath(from,to){
 const start=edgeAnchor(from,true),end=edgeAnchor(to),dx=Math.max(35,(end.x-start.x)*.5);
 const d=start.y===end.y&&end.x>=start.x?'M '+start.x+' '+start.y+' L '+end.x+' '+end.y:
   'M '+start.x+' '+start.y+' C '+(start.x+dx)+' '+start.y+', '+(end.x-dx)+' '+end.y+', '+end.x+' '+end.y;
 return {d,x:(start.x+end.x)/2,y:(start.y+end.y)/2};
}
function roundedRoute(points){
 let d='M '+points[0].x+' '+points[0].y;
 for(let i=1;i<points.length-1;i++){
   const p=points[i],prev=points[i-1],next=points[i+1],before=Math.hypot(p.x-prev.x,p.y-prev.y),after=Math.hypot(next.x-p.x,next.y-p.y),r=Math.min(10,before/2,after/2);
   if(!r){d+=' L '+p.x+' '+p.y;continue;}
   const a={x:p.x+(prev.x-p.x)*r/before,y:p.y+(prev.y-p.y)*r/before},b={x:p.x+(next.x-p.x)*r/after,y:p.y+(next.y-p.y)*r/after};
   d+=' L '+a.x+' '+a.y+' Q '+p.x+' '+p.y+' '+b.x+' '+b.y;
 }
 const end=points.at(-1);return d+' L '+end.x+' '+end.y;
}
function actionJunction(a,states){
 const getState=id=>states.find(n=>n.id===id);
 const target=getState(a.to),end=edgeAnchor(target),junction={x:end.x-44,y:end.y};
 const sources=a.from.map(id=>getState(id));
 const inputs=sources.map((s,index)=>{
   const start=edgeAnchor(s,true),left=Math.min(start.x,junction.x),right=Math.max(start.x,junction.x);
   const candidates=states.filter(n=>n.id!==s.id&&n.id!==target.id&&n.x<right&&n.x+W>left);
   const blocked=candidates.some(n=>n.y-12<Math.max(start.y,junction.y)&&n.y+H+12>Math.min(start.y,junction.y));
   if(!blocked&&junction.x>start.x){
     const dx=Math.max(20,(junction.x-start.x)*.5);
     return {id:s.id,d:'M '+start.x+' '+start.y+' C '+(start.x+dx)+' '+start.y+', '+(junction.x-dx)+' '+junction.y+', '+junction.x+' '+junction.y};
   }
   // An ancestor input can span intermediate result cards. Route above them,
   // retaining the recorded dependency rather than concealing it behind a card.
   const lane=Math.min(s.y,target.y,...candidates.map(n=>n.y))-28-index*16;
   const points=[start,{x:start.x+20,y:start.y},{x:start.x+20,y:lane},{x:junction.x-20,y:lane},{x:junction.x-20,y:junction.y},junction];
   return {id:s.id,d:roundedRoute(points),points};
 });
 const nearest=sources.reduce((best,n)=>Math.abs(edgeAnchor(n,true).x-junction.x)<Math.abs(edgeAnchor(best,true).x-junction.x)?n:best);
 return {inputs,junction,output:'M '+junction.x+' '+junction.y+' L '+end.x+' '+end.y,
   label:{x:(edgeAnchor(nearest,true).x+junction.x)/2,y:Math.min(nearest.y,target.y)-14}};
}
// Cards share one size across statuses, so matching a corresponding edge or
// center yields the same position. Use a center guide between the cards.
function alignment(position, states, scale, previous = {}, bypass = false) {
 const result = {x: position.x, y: position.y, guides: {}};
 if (bypass) return result;

 const snap = 6 / scale, release = 9 / scale, nearby = 240 / scale;
 for (const [axis, cross, size, crossSize] of [["x", "y", W, H], ["y", "x", H, W]]) {
   let best;
   for (const state of states) {
     if (state.id === position.id) continue;
     const delta = Math.abs(state[axis] - position[axis]);
     const separation = Math.abs(state[cross] - position[cross]);
     const gap = Math.max(0, separation - crossSize);
     const retained = previous[axis]?.id === state.id;
     // Only align with a neighbor in the perpendicular direction.
     if (separation < crossSize / 2 || gap > nearby || delta > (retained ? release : snap)) continue;
     if (!best || retained || (!best.retained && (
       delta < best.delta || (delta === best.delta && (
         separation < best.separation || (separation === best.separation && state.id < best.state.id)
       ))
     ))) best = {state, delta, separation, retained};
   }
   if (best) {
     result[axis] = best.state[axis];
     result.guides[axis] = {id: best.state.id, at: best.state[axis] + size / 2};
   }
 }
 for (const [axis, cross, crossSize] of [["x", "y", H], ["y", "x", W]]) {
   const guide = result.guides[axis];
   if (!guide) continue;
   const neighbor = states.find(state => state.id === guide.id);
   const padding = 8 / scale;
   guide.start = Math.min(neighbor[cross], result[cross]) - padding;
   guide.end = Math.max(neighbor[cross], result[cross]) + crossSize + padding;
 }
 return result;
}
// Layer each connected group, then order its rows using neighboring layers.
function autoArrange(states, actions) {
 const ids = states.map(state => state.id).sort();
 const parents = new Map(ids.map(id => [id, new Set()]));
 const children = new Map(ids.map(id => [id, new Set()]));
 for (const action of actions) {
   for (const parent of action.from) {
     parents.get(action.to).add(parent);
     children.get(parent).add(action.to);
   }
 }

 const depths = new Map(ids.map(id => [id, 0]));
 const remaining = new Map(ids.map(id => [id, parents.get(id).size]));
 const queue = ids.filter(id => remaining.get(id) === 0);
 for (let index = 0; index < queue.length; index++) {
   const id = queue[index];
   for (const child of children.get(id)) {
     depths.set(child, Math.max(depths.get(child), depths.get(id) + 1));
     remaining.set(child, remaining.get(child) - 1);
     if (remaining.get(child) === 0) queue.push(child);
   }
 }
 if (queue.length !== ids.length) throw new Error("Auto-arrange requires a graph without cycles.");

 const positions = new Map(), visited = new Set(), isolated = [];
 const columnGap = W + 120, rowGap = H + 72, margin = 64;
 let top = margin;
 for (const start of ids) {
   if (visited.has(start)) continue;
   if (!parents.get(start).size && !children.get(start).size) {
     isolated.push(start);
     continue;
   }
   const group = [start], layers = [];
   visited.add(start);
   for (let index = 0; index < group.length; index++) {
     const id = group[index], depth = depths.get(id);
     (layers[depth] ??= []).push(id);
     for (const neighbor of [...parents.get(id), ...children.get(id)]) {
       if (visited.has(neighbor)) continue;
       visited.add(neighbor);
       group.push(neighbor);
     }
   }

   const rows = new Map();
   function placeRows(layer) {
     layer.forEach((id, index) => rows.set(id, index - (layer.length - 1) / 2));
   }
   for (const layer of layers) {
     layer.sort();
     placeRows(layer);
   }
   function orderLayer(layer, neighbors) {
     const centers = new Map(layer.map(id => {
       const adjacent = [...neighbors.get(id)].sort();
       const center = adjacent.length
         ? adjacent.reduce((sum, neighbor) => sum + rows.get(neighbor), 0) / adjacent.length
         : rows.get(id);
       return [id, center];
     }));
     // Stable sorting preserves the previous order when two branches tie.
     layer.sort((a, b) => centers.get(a) - centers.get(b));
     placeRows(layer);
   }
   for (let pass = 0; pass < 4; pass++) {
     for (let i = 1; i < layers.length; i++) orderLayer(layers[i], parents);
     for (let i = layers.length - 2; i >= 0; i--) orderLayer(layers[i], children);
   }
   // Finish left to right so downstream order reflects the final parent order.
   for (let i = 1; i < layers.length; i++) orderLayer(layers[i], parents);

   const height = layers.reduce((max, layer) => Math.max(max, layer.length), 0);
   for (const id of group) {
     positions.set(id, {
       x: margin + depths.get(id) * columnGap,
       y: top + (rows.get(id) + (height - 1) / 2) * rowGap,
     });
   }
   top += height * rowGap + 48;
 }
 isolated.forEach((id, index) => positions.set(id, {
   x: margin + (index % 4) * columnGap,
   y: top + Math.floor(index / 4) * rowGap,
 }));
 return ids.map(id => ({id, ...positions.get(id)}));
}
return Object.freeze({W,H,edgeAnchor,edgePath,roundedRoute,actionJunction,alignment,autoArrange});
})();
