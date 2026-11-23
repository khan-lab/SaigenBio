"use strict";

globalThis.SaigenAnalysisGroups = (() => {
  const {W, H} = SaigenGeometry;
  const groupKey = id => "group:" + id;
  const countLabel = (count, noun, plural = noun + "s") => count + " " + (count === 1 ? noun : plural);

  function compactAt(scale, wasCompact, depth = 0) {
    const offset = .85 * (1 - .8 ** depth);
    return wasCompact ? scale < .65 + offset : scale <= .55 + offset;
  }

  const leftmost = (a, b) => !a || b.x < a.x || (b.x === a.x && b.y < a.y) ? b : a;

  function groupAt(group, occupied, scale) {
    // Anchor near a real member. Keep the summary legible at overview scale.
    const anchor = group.anchor;
    const width = Math.max(W, 112 / scale);
    const height = Math.max(H, 65 / scale);
    const x = anchor.x;
    let y = anchor.y;
    while (true) {
      const blockers = occupied.filter(box =>
        x < box.x + (box.width ?? W) + 10 && x + width + 10 > box.x &&
        y < box.y + (box.height ?? H) + 10 && y + height + 10 > box.y);
      if (!blockers.length) break;
      y = Math.max(...blockers.map(box => box.y + (box.height ?? H) + 10));
    }
    return {...group, id: groupKey(group.id), groupId: group.id, x, y, width, height,
      fontScale: Math.max(1, .56 / scale), anchorId: anchor.id};
  }

  function hierarchy(groups, byId, {overrides, automatic, full, scale}) {
    const children = new Map();
    for (const group of groups) {
      const parent = group.parentId ?? null;
      if (!children.has(parent)) children.set(parent, []);
      children.get(parent).push(group);
    }
    const endpoint = new Map();
    const ordered = [];
    const stack = (children.get(null) || []).map(group => ({group, parent: null})).reverse();
    while (stack.length) {
      const {group, parent} = stack.pop();
      const depth = parent ? parent.depth + 1 : 0;
      const zoom = compactAt(scale, automatic.get(group.id), depth);
      automatic.set(group.id, zoom);
      const collapsed = !full && (overrides.get(group.id) ?? zoom);
      const hiddenBy = parent ? parent.hiddenBy || (parent.collapsed ? parent.id : null) : null;
      const covering = hiddenBy || (collapsed ? group.id : null);
      const entry = {...group, depth, collapsed, hiddenBy, parentTitle:parent?.title,
        count:0, failed:0, running:0, anchor:null};
      for (const id of group.stateIds) {
        const member = byId.get(id);
        if (!member) continue;
        entry.count++;
        if (member.status === "failed") entry.failed++;
        if (member.status === "running") entry.running++;
        entry.anchor = leftmost(entry.anchor, member);
        if (covering) endpoint.set(id, groupKey(covering));
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
    }
    return {groups: ordered.map(({entry}) => entry).filter(group => group.count), endpoint};
  }

  function project(flow, options) {
    const byId = new Map(flow.states.map(node => [node.id, node]));
    const {groups, endpoint} = hierarchy(flow.analysisGroups || [], byId, options);
    const states = endpoint.size ? flow.states.filter(node => !endpoint.has(node.id)) : flow.states;
    const placed = [...states];
    const summaries = groups.filter(group => group.collapsed && !group.hiddenBy).map(group => {
      const summary = groupAt(group, placed, options.scale);
      placed.push(summary);
      byId.set(summary.id, summary);
      return summary;
    });
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
    return {states, groups, summaries, actions, connections: [...connections.values()], endpoint, placed};
  }

  function status(group) {
    return [group.running && countLabel(group.running, "running result"),
      group.failed && countLabel(group.failed, "failed result")].filter(Boolean).join(" · ");
  }

  function card(group, esc) {
    const detail = status(group);
    return '<button type="button" class="analysis-group-card" data-analysis-group="'+esc(group.groupId)+
      '" aria-expanded="false" aria-label="'+esc("Expand "+group.title+(group.parentTitle?" in "+group.parentTitle:"")+
        ", "+countLabel(group.count,"result")+(detail ? ", "+detail : ""))+'">'+
      (group.parentTitle?'<span class="group-card-parent">'+esc(group.parentTitle)+'</span>':"")+
      '<span class="group-card-title">'+esc(group.title)+
      '</span><span class="group-card-meta">'+countLabel(group.count,"result")+
      '</span>'+(detail?'<span class="group-card-status">'+esc(detail)+'</span>':"")+'</button>';
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

  function groupList(groups, hasOverrides, esc) {
    if (!groups.length) return "<p>No analysis groups are saved.</p>";
    return '<p class="group-dialog-help">Level of detail follows zoom. Use a manual choice for this tab, or return to automatic.</p>'+
      '<ul class="group-dialog-list">'+groups.map(group => {
        const label = group.hiddenBy ? "Reveal" : group.collapsed ? "Expand" : "Collapse";
        return '<li style="padding-inline-start:'+Math.min(group.depth,5)*13+'px"><div><strong>'+esc(group.title)+'</strong><small>'+countLabel(group.count,"result")+
        (status(group)?" · "+esc(status(group)):"")+'</small>'+
        (group.reason?'<p>'+esc(group.reason)+'</p>':"")+'</div><button class="outline" data-toggle-analysis-group="'+
        esc(group.id)+'" aria-expanded="'+(!group.collapsed&&!group.hiddenBy)+'" aria-label="'+
        esc(label+" "+group.title)+'">'+label+'</button><button class="outline" data-group-pipeline="'+esc(group.id)+'" aria-label="'+esc("Create pipeline from "+group.title)+'">Create pipeline…</button></li>';
      }).join("")+
      '</ul><button class="outline" data-reset-analysis-groups'+(hasOverrides?"":" disabled")+'>Use zoom</button>';
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

  return {compactAt, project, card, edge, groupList, dependencyList};
})();
