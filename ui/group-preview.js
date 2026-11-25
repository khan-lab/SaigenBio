"use strict";

globalThis.SaigenGroupPreview = (() => {
  const {W, H, edgePath, actionJunction} = SaigenGeometry;
  const OPEN_DELAY = 400, CLOSE_DELAY = 180, GAP = 8, MARGIN = 12, PADDING = 24;

  function project(flow, groupId) {
    const nodes = SaigenAnalysisGroups.memberStates(flow, groupId);
    const byId = new Map(nodes.map(node => [node.id, node]));
    const actions = flow.actions
      .filter(action => byId.has(action.to))
      .map(action => ({...action, from: action.from.filter(id => byId.has(id))}))
      .filter(action => action.from.length);
    return {nodes, actions, byId};
  }

  function graphMarkup({nodes, actions, byId}, bounds, esc) {
    const path = (d, kind, arrow) => '<path class="edge-line '+kind+'" d="'+d+'"'+
      (arrow?' marker-end="url(#group-preview-arrow)"':'')+'/>';
    const edges = actions.map(action => {
      const kind = action.status === "running" ? "running-edge" : action.status === "planned" ? "planned-edge" : "";
      if (action.from.length === 1) return path(edgePath(byId.get(action.from[0]), byId.get(action.to)).d, kind, true);
      const join = actionJunction(action, nodes);
      return join.inputs.map(input => path(input.d, kind, false)).join("")+
        path(join.output, kind, true)+'<circle class="edge-junction" cx="'+join.junction.x+'" cy="'+join.junction.y+'" r="3.5"/>';
    }).join("");
    const cards = nodes.map(node => '<li class="group-preview-node '+esc(node.status)+'" style="left:'+
      (node.x-bounds.x)+'px;top:'+(node.y-bounds.y)+'px;width:'+(node.width??W)+'px;height:'+(node.height??H)+'px">'+
      '<strong title="'+esc(node.title)+'">'+esc(node.title)+'</strong>'+
      (node.status?'<span>'+esc(node.status)+'</span>':'')+'</li>').join("");
    const dependencies = actions.map(action => '<li>'+esc(action.from.map(id => byId.get(id).title).join(" + "))+
      ' → '+esc(byId.get(action.to).title)+'</li>').join("");
    return '<svg class="group-preview-edges" aria-hidden="true" width="'+bounds.w+'" height="'+bounds.h+'" viewBox="'+
      [bounds.x,bounds.y,bounds.w,bounds.h].join(" ")+'"><defs><marker id="group-preview-arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto"><path d="M1 1L7 4L1 7" fill="none" stroke="#728a76" stroke-width="1.2"/></marker></defs>'+
      edges+'</svg><ul class="group-preview-nodes" aria-label="Group members">'+cards+'</ul>'+
      (dependencies?'<ul class="visually-hidden" aria-label="Internal connections">'+dependencies+'</ul>':'');
  }

  function position(rect, width, height, viewportWidth, viewportHeight) {
    const clamp = (value, high) => Math.max(MARGIN, Math.min(high, value));
    const right = viewportWidth-rect.right-MARGIN-GAP;
    const left = rect.left-MARGIN-GAP;
    if (right >= width || left >= width) return {
      x: right >= width ? rect.right+GAP : rect.left-width-GAP,
      y: clamp(rect.top, viewportHeight-height-MARGIN),
      maxHeight: viewportHeight-2*MARGIN,
    };
    const below = viewportHeight-rect.bottom-MARGIN-GAP;
    const above = rect.top-MARGIN-GAP;
    const useBelow = below >= height || below >= above;
    const room = useBelow ? below : above;
    const maxHeight = Math.min(viewportHeight-2*MARGIN, Math.max(150, room));
    const fittedHeight = Math.min(height, maxHeight);
    return {
      x: clamp((rect.left+rect.right-width)/2, viewportWidth-width-MARGIN),
      y: clamp(useBelow ? rect.bottom+GAP : rect.top-GAP-fittedHeight, viewportHeight-fittedHeight-MARGIN),
      maxHeight,
    };
  }

  function create({root, panel, getFlow, getGroup, enabled, openGroup, boundsFor, escape: esc, onShow}) {
    if (typeof panel.showPopover !== "function") return Object.freeze({close() {}, show() {}});
    const cardSelector = "[data-analysis-group]";
    const graph = panel.querySelector(".group-preview-graph");
    const scene = panel.querySelector(".group-preview-scene");
    const stage = panel.querySelector(".group-preview-stage");
    const openButton = panel.querySelector("[data-open-group]");
    let anchor = null, opener = null, mode = null, pending = null, closeTimer = null, restoring = false;

    function cancelPending() {
      if (pending) clearTimeout(pending.timer);
      pending = null;
    }

    function close(restoreFocus = false) {
      cancelPending();
      clearTimeout(closeTimer);
      if (!anchor) return false;
      const previous = opener;
      anchor.closest(".analysis-group-slot")?.querySelector("[data-preview-group]").setAttribute("aria-expanded", "false");
      anchor.removeAttribute("aria-describedby");
      anchor = opener = mode = null;
      panel.hidePopover();
      panel.hidden = true;
      panel.remove();
      if (restoreFocus && previous.isConnected) {
        restoring = true;
        previous.focus({preventScroll:true});
        restoring = false;
      }
      return true;
    }

    function show(card, source, trigger = card) {
      if (!enabled() || !card.isConnected || restoring) return;
      if (card === anchor && mode === source) return;
      const group = getGroup(card.dataset.analysisGroup);
      if (!group) return;
      const view = project(getFlow(), group.groupId);
      if (!view.nodes.length) return;
      close();
      onShow();
      anchor = card;
      opener = trigger;
      mode = source;
      panel.querySelector("h2").textContent = group.title;
      panel.querySelector(".group-preview-count").textContent = view.nodes.length+(view.nodes.length === 1 ? " result" : " results");
      const box = boundsFor(view.nodes);
      const bounds = {x:box.x-PADDING, y:box.y-PADDING, w:box.w+2*PADDING, h:box.h+2*PADDING};
      stage.innerHTML = graphMarkup(view, bounds, esc);
      card.after(panel);
      card.setAttribute("aria-describedby", "group-preview-instructions");
      trigger.closest(".analysis-group-slot")?.querySelector("[data-preview-group]").setAttribute("aria-expanded", "true");
      panel.style.maxHeight = "";
      graph.style.height = graph.style.maxHeight = "";
      panel.hidden = false;
      panel.showPopover();

      const width = panel.clientWidth;
      const header = panel.querySelector(".group-preview-header").offsetHeight;
      // Keep titles at least 13 px. Scroll the full graph when it cannot fit.
      const scale = Math.max(.85, Math.min(1, (width-2)/bounds.w, graph.clientHeight/bounds.h));
      Object.assign(stage.style, {width:bounds.w+"px", height:bounds.h+"px", transform:"scale("+scale+")"});
      Object.assign(scene.style, {width:Math.ceil(bounds.w*scale)+"px", height:Math.ceil(bounds.h*scale)+"px"});
      graph.style.height = Math.ceil(bounds.h*scale)+"px";
      const location = position(card.getBoundingClientRect(), panel.offsetWidth, panel.offsetHeight, innerWidth, innerHeight);
      Object.assign(panel.style, {left:location.x+"px", top:location.y+"px", maxHeight:location.maxHeight+"px"});
      graph.style.maxHeight = "min(350px, 48dvh, "+Math.max(0, location.maxHeight-header-2)+"px)";
      graph.scrollTo(0, 0);
      const scrollable = graph.scrollWidth>graph.clientWidth || graph.scrollHeight>graph.clientHeight;
      graph.tabIndex = scrollable ? 0 : -1;
      panel.querySelector(".group-preview-count").textContent += scrollable ? " · Scroll to explore" : "";
      if (source === "touch") openButton.focus({preventScroll:true});
    }

    function scheduleClose() {
      clearTimeout(closeTimer);
      closeTimer = setTimeout(() => {
        if (mode === "pointer" && !panel.contains(document.activeElement)) close();
      }, CLOSE_DELAY);
    }

    root.addEventListener("pointerover", event => {
      const card = event.target.closest(cardSelector);
      if (!card || event.pointerType === "touch" || card.contains(event.relatedTarget)) return;
      if (anchor === card) { clearTimeout(closeTimer); return; }
      if (mode && mode !== "pointer") return;
      cancelPending();
      pending = {card, timer:setTimeout(() => {
        pending = null;
        show(card, "pointer");
      }, OPEN_DELAY)};
    });
    root.addEventListener("pointerout", event => {
      const card = event.target.closest(cardSelector);
      if (!card || card.contains(event.relatedTarget)) return;
      if (pending?.card === card) cancelPending();
      if (anchor === card && !panel.contains(event.relatedTarget)) scheduleClose();
    });
    root.addEventListener("focusin", event => {
      if (event.target.matches(cardSelector+":focus-visible")) show(event.target, "keyboard");
    });
    root.addEventListener("focusout", event => {
      if ((!anchor || event.target !== opener && event.target !== anchor && !panel.contains(event.target)) ||
          panel.contains(event.relatedTarget) || event.relatedTarget === anchor || event.relatedTarget === opener) return;
      close();
    });
    panel.addEventListener("pointerenter", () => clearTimeout(closeTimer));
    panel.addEventListener("pointerleave", event => {
      if (!anchor?.contains(event.relatedTarget)) scheduleClose();
    });
    document.addEventListener("pointerdown", event => {
      if (!panel.contains(event.target) && !anchor?.contains(event.target) && !event.target.closest("[data-preview-group]")) close();
    });
    document.addEventListener("keydown", event => {
      if (event.key !== "Escape" || !anchor) return;
      event.preventDefault();
      close(panel.contains(document.activeElement));
    });
    panel.querySelector("[data-close-group-preview]").onclick = () => close(true);
    openButton.onclick = () => {
      const id = anchor.dataset.analysisGroup;
      close();
      openGroup(id);
    };
    return Object.freeze({close, show});
  }

  return Object.freeze({create, project, position});
})();
