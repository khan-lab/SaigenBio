"use strict";

// Pure canvas geometry. Inputs are recorded states; no DOM or application state.
globalThis.SaigenGeometry = (() => {
const W=192,H=132;
function edgeAnchor(n,right=false){return {x:n.x+(right?(n.width??W):0),y:n.y+(n.height??H)/2};}
function edgePath(from,to){
 const start=edgeAnchor(from,true),end=edgeAnchor(to),dx=Math.max(35,(end.x-start.x)*.5);
 const d=start.y===end.y&&end.x>=start.x?'M '+start.x+' '+start.y+' L '+end.x+' '+end.y:
   'M '+start.x+' '+start.y+' C '+(start.x+dx)+' '+start.y+', '+(end.x-dx)+' '+end.y+', '+end.x+' '+end.y;
 return {d,x:(start.x+end.x)/2,y:(start.y+end.y)/2};
}
const point = (x, y) => ({x, y});
const midpoint = (a, b) => point((a.x + b.x) / 2, (a.y + b.y) / 2);

function forwardCurve(start, end) {
 const handle = (end.x - start.x) / 2;
 return [start, point(start.x + handle, start.y), point(end.x - handle, end.y), end];
}

// A cubic lies inside its control-point bounds. Subdivide overlapping bounds
// until they clear the box or are small enough to count as a collision.
function touchesBox(curve, box, depth = 0) {
 const left = Math.min(...curve.map(p => p.x)), right = Math.max(...curve.map(p => p.x));
 const top = Math.min(...curve.map(p => p.y)), bottom = Math.max(...curve.map(p => p.y));
 if (right < box.left || left > box.right || bottom < box.top || top > box.bottom) return false;
 if (depth === 9 || (left >= box.left && right <= box.right && top >= box.top && bottom <= box.bottom)) return true;
 const [a, b, c, d] = curve;
 const ab = midpoint(a, b), bc = midpoint(b, c), cd = midpoint(c, d);
 const abc = midpoint(ab, bc), bcd = midpoint(bc, cd), center = midpoint(abc, bcd);
 return touchesBox([a, ab, abc, center], box, depth + 1)
   || touchesBox([center, bcd, cd, d], box, depth + 1);
}

function smoothDetour(start, end, left, right, lane) {
 const entry = point(left, lane), exit = point(right, lane);
 return [forwardCurve(start, entry), forwardCurve(entry, exit), forwardCurve(exit, end)];
}

function backwardDetour(start, end, lane) {
 const entry = point(start.x, lane), exit = point(end.x, lane);
 const turn = 40;
 return [
   [start, point(start.x + turn, start.y), point(entry.x + turn, lane), entry],
   forwardCurve(entry, exit),
   [exit, point(exit.x - turn, lane), point(end.x - turn, end.y), end],
 ];
}

function junctionRoute(start, end, boxes, source, target, index) {
 const forward = end.x > start.x;
 const direct = forwardCurve(start, end);
 const blocking = forward ? boxes.filter(box => touchesBox(direct, box)) : [];
 if (forward && !blocking.length) return [direct];

 const candidates = [];
 function add(curves, lane) {
   const cost = Math.abs(lane - start.y) + Math.abs(lane - end.y);
   candidates.push({curves, cost});
 }
 const clearance = 12 + (index % 4) * 5;
 if (forward) {
   // Try passing only the cards the direct curve hits. Also try wider lanes
   // when other cards would obstruct the entry, exit, or the detour itself.
   const nearby = boxes.filter(box => box.left < end.x && box.right > start.x);
   for (const obstacles of [blocking, nearby]) {
     const left = Math.max(start.x, Math.min(...obstacles.map(box => box.left)));
     const right = Math.min(end.x, Math.max(...obstacles.map(box => box.right)));
     for (const lane of [
       Math.min(...obstacles.map(box => box.top)) - clearance,
       Math.max(...obstacles.map(box => box.bottom)) + clearance,
     ]) add(smoothDetour(start, end, left, right, lane), lane);
   }
 } else {
   const nearby = boxes.filter(box => box.left <= start.x + 40 && box.right >= end.x - 40);
   const top = Math.min(source.y, target.y, ...nearby.map(box => box.top));
   const bottom = Math.max(source.y + (source.height ?? H), target.y + (target.height ?? H), ...nearby.map(box => box.bottom));
   for (const lane of [top - clearance, bottom + clearance]) add(backwardDetour(start, end, lane), lane);
 }
 candidates.sort((a, b) => a.cost - b.cost);
 const clear = candidates.find(({curves}) =>
   curves.every(curve => boxes.every(box => !touchesBox(curve, box))));
 // Manual card overlaps can leave no visible exit or entrance.
 return (clear || candidates[0]).curves;
}

function cubicPath(curves) {
 const [start] = curves[0];
 const points = curve => curve.slice(1).map(p => p.x + " " + p.y).join(", ");
 return "M " + start.x + " " + start.y + curves.map(curve => " C " + points(curve)).join("");
}
function actionJunction(a,states){
 const getState=id=>states.find(n=>n.id===id);
 const target=getState(a.to),end=edgeAnchor(target),junction={x:end.x-44,y:end.y};
 const sources=a.from.map(id=>getState(id));
 const inputs=sources.map((s,index)=>{
   const start = edgeAnchor(s, true);
   const boxes = states.filter(n => n.id !== s.id && n.id !== target.id).map(n => ({
     left: n.x - 8, right: n.x + (n.width ?? W) + 8, top: n.y - 8, bottom: n.y + (n.height ?? H) + 8,
   }));
   return {id: s.id, d: cubicPath(junctionRoute(start, junction, boxes, s, target, index))};
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
return Object.freeze({W,H,edgeAnchor,edgePath,actionJunction,alignment,autoArrange});
})();
