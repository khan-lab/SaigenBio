"use strict";

globalThis.SaigenAnalysisGroups = (() => {
  const {W, H} = SaigenGeometry;
  const groupKey = id => "group:" + id;
  const countLabel = (count, noun, plural = noun + "s") => count + " " + (count === 1 ? noun : plural);

  const leftmost = (a, b) => !a || b.x < a.x || (b.x === a.x && b.y < a.y) ? b : a;

  function newerFigure(current, candidate) {
    if (!candidate) return current;
    if (!current || candidate.date > current.date ||
        (candidate.date === current.date && candidate.node.id < current.node.id)) return candidate;
    return current;
  }

  function groupAt(group, scale) {
    const width = Math.max(W, 112 / scale) + (group.figure ? Math.max(W * .7, 76 / scale) : 0);
    const height = Math.max(H, 65 / scale);
    const box = group.bounds;
    return {...group, id: groupKey(group.id), groupId: group.id,
      x:(box.left+box.right-width)/2, y:(box.top+box.bottom-height)/2, width, height,
      fontScale:Math.max(1, .56 / scale)};
  }

  function childrenByParent(groups) {
    const children = new Map();
    for (const group of groups) {
      const parent = group.parentId ?? null;
      if (!children.has(parent)) children.set(parent, []);
      children.get(parent).push(group);
    }
    return children;
  }

  function includeBox(a, b) {
    return a ? {left:Math.min(a.left,b.left), top:Math.min(a.top,b.top),
      right:Math.max(a.right,b.right), bottom:Math.max(a.bottom,b.bottom)} : b;
  }

  function hierarchy(groups, byId, {full, figureFor}) {
    const children = childrenByParent(groups);
    const endpoint = new Map();
    const ordered = [];
    const stack = (children.get(null) || []).map(group => ({group, parent: null})).reverse();
    while (stack.length) {
      const {group, parent} = stack.pop();
      const topId = parent?.topId ?? group.id;
      const entry = {...group, topId, count:0, failed:0, running:0, anchor:null, bounds:null, figure:null};
      for (const id of group.stateIds) {
        const member = byId.get(id);
        if (!member) continue;
        entry.count++;
        if (member.status === "failed") entry.failed++;
        if (member.status === "running") entry.running++;
        entry.anchor = leftmost(entry.anchor, member);
        entry.bounds = includeBox(entry.bounds,{left:member.x,top:member.y,right:member.x+W,bottom:member.y+H});
        if (!full) {
          endpoint.set(id, groupKey(topId));
          if (["completed", "imported", "saved"].includes(member.status)) {
            const artifact = figureFor?.(member);
            if (artifact) {
              const date = Date.parse(member.finishedAt || member.createdAt) || 0;
              entry.figure = newerFigure(entry.figure, {node: member, artifact, date});
            }
          }
        }
      }
      ordered.push({entry, parent});
      const descendants = children.get(group.id) || [];
      for (let i = descendants.length - 1; i >= 0; i--) stack.push({group: descendants[i], parent: entry});
    }
    for (let i = ordered.length - 1; i >= 0; i--) {
      const {entry, parent} = ordered[i];
      if (!parent || !entry.count) continue;
      parent.count += entry.count;
      parent.failed += entry.failed;
      parent.running += entry.running;
      parent.anchor = leftmost(parent.anchor, entry.anchor);
      parent.bounds = includeBox(parent.bounds,entry.bounds);
      parent.figure = newerFigure(parent.figure, entry.figure);
    }
    return {groups: ordered.map(({entry}) => entry).filter(group => group.count), endpoint};
  }

  function path(groups, stateId) {
    const byId = new Map(groups.map(group => [group.id,group]));
    const result = [];
    for(let group=groups.find(item=>item.stateIds.includes(stateId));group;group=byId.get(group.parentId)){
      result.push(group);
    }
    return result.reverse();
  }

  function memberIds(groups, groupId) {
    const root = groups.find(group => group.id === groupId);
    if (!root) return new Set();
    const children = childrenByParent(groups);
    const ids = new Set(), queue = [root];
    while(queue.length){
      const group=queue.pop();
      for(const id of group.stateIds)ids.add(id);
      for(const child of children.get(group.id)??[])queue.push(child);
    }
    return ids;
  }

  function memberStates(flow, groupId) {
    const members = memberIds(flow.analysisGroups??[], groupId);
    return flow.states.filter(node => members.has(node.id));
  }

  function translate(view, moves) {
    const byId = new Map(moves.map(move => [move.id, move]));
    const operations = [];
    for (const node of view.byId.values()) {
      const move = byId.get(view.endpoint.get(node.id) ?? node.id);
      if (node.groupId || !move || (!move.dx && !move.dy)) continue;
      operations.push({op:"edit_state",id:node.id,changes:{x:node.x+move.dx,y:node.y+move.dy}});
    }
    return operations;
  }

  function groupSize(scale) {
    return {width:Math.max(W, 112 / scale) + Math.max(W * .7, 76 / scale),
      height:Math.max(H, 65 / scale)};
  }

  function arrange(view, scale) {
    const ids = view.placed.map(card => card.id).sort();
    const children = new Map(ids.map(id => [id, new Set()]));
    const parentCounts = new Map(ids.map(id => [id, 0]));
    for (const {from, to} of [...view.actions, ...view.connections.map(edge =>
      ({from:[edge.from.id], to:edge.to.id}))]) {
      for (const source of from) {
        if (children.get(source).has(to)) continue;
        children.get(source).add(to);
        parentCounts.set(to, parentCounts.get(to) + 1);
      }
    }
    // A collapsed group can create a cycle in the projection. Ignore DFS
    // back edges for ranking only. The edge renderer still uses every link.
    const active = new Set(), done = new Set(), ordered = [];
    ids.sort((a, b) => parentCounts.get(a) - parentCounts.get(b));
    for (const root of ids) {
      if (done.has(root)) continue;
      active.add(root);
      const stack = [{id:root, links:[...children.get(root)].sort().values()}];
      while (stack.length) {
        const top = stack.at(-1), next = top.links.next();
        if (next.done) {
          active.delete(top.id);
          done.add(top.id);
          stack.pop();
        } else if (!active.has(next.value)) {
          ordered.push({from:[top.id], to:next.value});
          if (!done.has(next.value)) {
            active.add(next.value);
            stack.push({id:next.value, links:[...children.get(next.value)].sort().values()});
          }
        }
      }
    }
    const {width, height} = groupSize(scale);
    return {scale, cards:SaigenGeometry.autoArrange(view.placed, ordered, {
      boxWidth:Math.ceil(width), boxHeight:Math.ceil(height)
    })};
  }

  function project(flow, options) {
    const byId = new Map(flow.states.map(node => [node.id, node]));
    const {groups, endpoint} = hierarchy(flow.analysisGroups || [], byId, options);
    const states = endpoint.size ? flow.states.filter(node => !endpoint.has(node.id)) : flow.states;
    const summaries = options.full ? [] : groups.filter(group => !group.parentId).map(group => groupAt(group,options.scale));
    for(const summary of summaries)byId.set(summary.id,summary);
    const placed = [...states,...summaries];
    const actions = [];
    const connections = new Map();
    for (const action of flow.actions) {
      const target = endpoint.get(action.to) ?? action.to;
      if (target === action.to && action.from.every(id => !endpoint.has(id))) {
        actions.push(action);
        continue;
      }
      for (const sourceId of action.from) {
        const source = endpoint.get(sourceId) ?? sourceId;
        if (source === target) continue;
        const key = JSON.stringify([source, target]);
        if (!connections.has(key)) connections.set(key, {from: byId.get(source), to: byId.get(target), links: []});
        connections.get(key).links.push({action, source: byId.get(sourceId), target: byId.get(action.to)});
      }
    }
    return {states, groups, summaries, actions, connections: [...connections.values()], endpoint, placed, byId};
  }

  function card(group, esc, imagePreview) {
    const counts = [
      ["running", group.running, "running result"],
      ["failed", group.failed, "failed result"],
    ].filter(([, count]) => count > 0).map(([kind, count, noun]) => [kind, countLabel(count, noun)]);
    const detail = counts.map(([, label]) => label).join(" · ");
    const status = counts.map(([kind, label]) => '<span class="group-card-'+kind+'">'+esc(label)+'</span>').join(" · ");
    const source = group.figure?.node;
    const preview = source && imagePreview ? '<span class="group-card-figure">'+
      imagePreview(source, "group-card-thumbnail")+'<span class="group-card-source" title="'+esc(source.title)+'">'+
      esc(source.title)+'</span></span>' : "";
    const label = "Show nodes in "+group.title+
      ", "+countLabel(group.count,"result")+(detail ? ", "+detail : "")+
      (preview ? ", figure from "+source.title : "");
    return '<button type="button" class="analysis-group-card'+(preview?' has-group-figure':'')+
      '" data-analysis-group="'+esc(group.groupId)+'" aria-label="'+esc(label)+
      '" aria-keyshortcuts="Shift+ArrowUp Shift+ArrowDown Shift+ArrowLeft Shift+ArrowRight" title="Click to show individual nodes. Drag or use Shift+arrow keys to move.">'+
      '<span class="group-card-summary">'+
      '<span class="group-card-title">'+esc(group.title)+
      '</span><span class="group-card-meta">'+countLabel(group.count,"result")+
      '</span>'+(status?'<span class="group-card-status">'+status+'</span>':"")+'</span>'+preview+'</button>';
  }

  function connectionPath(from, to) {
    const a = {x: from.x+(from.width??W)/2, y: from.y+(from.height??H)/2};
    const b = {x: to.x+(to.width??W)/2, y: to.y+(to.height??H)/2};
    if (from.x+(from.width??W) <= to.x || to.x+(to.width??W) <= from.x) {
      const forward = a.x <= b.x;
      const start = forward ? from.x+(from.width??W) : from.x;
      const end = forward ? to.x : to.x+(to.width??W);
      const mid = (start+end)/2;
      const lane = forward ? -10 : 10;
      return `M ${start} ${a.y+lane} C ${mid} ${a.y+lane}, ${mid} ${b.y+lane}, ${end} ${b.y+lane}`;
    }
    const down = a.y <= b.y;
    const start = down ? from.y+(from.height??H) : from.y;
    const end = down ? to.y : to.y+(to.height??H);
    const mid = (start+end)/2;
    const lane = down ? 10 : -10;
    return `M ${a.x+lane} ${start} C ${a.x+lane} ${mid}, ${b.x+lane} ${mid}, ${b.x+lane} ${end}`;
  }

  function edge(connection, index, esc) {
    const {from, to, links} = connection;
    const path = connectionPath(from, to);
    const label = countLabel(links.length, "dependency", "dependencies");
    return '<g class="edge-group summary-edge" role="button" tabindex="0" data-group-edge="'+index+
      '" aria-label="'+esc(label+" from "+from.title+" to "+to.title)+'"><title>'+esc(label)+
      '</title><path class="edge-line" d="'+path+'" marker-end="url(#arrow)"/><path class="edge-hit" d="'+path+'"/></g>';
  }

  function dependencyList(connection, esc) {
    const entries = new Map();
    for (const link of connection.links) {
      const group = entries.get(link.action.id) || [];
      group.push(link);
      entries.set(link.action.id, group);
    }
    return '<p class="group-dialog-help">'+esc(connection.from.title+" → "+connection.to.title)+'</p><ul class="group-dialog-list">'+
      [...entries.values()].map(links => {
        const {action, target} = links[0];
        return '<li><div><strong>'+esc(action.label)+'</strong><small>'+
          esc(links.map(link => link.source.title).join(" + ")+" → "+target.title)+'</small><small>'+
          esc(action.status+" · "+action.id)+'</small></div><button class="outline" data-group-target="'+esc(target.id)+
          '" aria-label="'+esc("Open "+target.title)+'">Open result</button></li>';
      }).join("")+'</ul>';
  }

  return {project, arrange, card, edge, dependencyList, path, memberIds, memberStates, translate};
})();
