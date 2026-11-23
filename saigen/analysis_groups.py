"""Persist an agreed Canvas organization alongside the analysis graph."""
from .records import ID, RecordError, text


def show(store):
    flow = store.flow()
    return {"revision": flow["revision"], "groups": flow.get("analysisGroups", [])}


def _ancestors(groups, seeds):
    """Collect seed groups and all their ancestors."""
    included = set()
    for ident in seeds:
        while ident is not None and ident not in included:
            included.add(ident)
            ident = groups[ident].get("parentId")
    return included


def _validate_hierarchy(groups):
    by_id = {group["id"]: group for group in groups}
    for group in groups:
        parent = group.get("parentId")
        if parent is not None and parent not in by_id:
            raise RecordError(f"Unknown parent group: {parent}")
    checked = set()
    for group in groups:
        path = set()
        ident = group["id"]
        while ident is not None and ident not in checked:
            if ident in path:
                raise RecordError("Groups cannot contain themselves or an ancestor")
            path.add(ident)
            ident = by_id[ident].get("parentId")
        checked.update(path)
    if len(_ancestors(by_id, (g["id"] for g in groups if g["stateIds"]))) != len(groups):
        raise RecordError("Every group needs a state or a subgroup containing states")


def replace(store, groups, revision, actor):
    if type(revision) is not int:
        raise RecordError("A project revision is required")
    if not isinstance(groups, list):
        raise RecordError("Supply a JSON list of analysis groups")

    def change(flow):
        known_states = {state["id"] for state in flow["states"]}
        group_ids, titles, assigned = set(), set(), set()
        normalized = []
        for group in groups:
            if (not isinstance(group, dict) or not {"id", "title", "stateIds"} <= group.keys()
                    or group.keys() - {"id", "title", "stateIds", "reason", "parentId"}):
                raise RecordError("Each group needs id, title and stateIds, with optional reason and parentId")
            ident, members = group["id"], group["stateIds"]
            title = text(group["title"], "group title", 120, True).strip()
            if not isinstance(ident, str) or not ID.fullmatch(ident) or ident in group_ids:
                raise RecordError("Use unique, valid group IDs")
            parent = group.get("parentId")
            if parent is not None and (not isinstance(parent, str) or not ID.fullmatch(parent)):
                raise RecordError(f"Invalid parent ID for {title}")
            title_key = (parent, title.casefold())
            if title_key in titles:
                raise RecordError("Use distinct titles for groups with the same parent")
            if not isinstance(members, list):
                raise RecordError(f"{title} needs a list of direct states")
            for state in members:
                if not isinstance(state, str) or state not in known_states:
                    raise RecordError(f"{title} contains an unknown state")
                if state in assigned:
                    raise RecordError(f"State {state} can only be assigned directly to one group")
                assigned.add(state)
            group_ids.add(ident)
            titles.add(title_key)
            reason = text(group.get("reason", ""), "group reason", 2000).strip()
            record = {"id": ident, "title": title, "stateIds": members, "reason": reason}
            if parent is not None:
                record["parentId"] = parent
            normalized.append(record)
        _validate_hierarchy(normalized)
        flow["analysisGroups"] = normalized
        return {"groups": normalized}, None

    flow = store.update("canvas.groups.updated", actor, change, revision)
    return {"revision": flow["revision"], "groups": flow["analysisGroups"]}


def remove_missing_members(flow, removed_ids):
    """Retire references when existing graph operations remove their states."""
    groups = flow.get("analysisGroups")
    if not groups or not removed_ids:
        return
    for group in groups:
        group["stateIds"] = [sid for sid in group["stateIds"] if sid not in removed_ids]
    by_id = {group["id"]: group for group in groups}
    retained = _ancestors(by_id, (group["id"] for group in groups if group["stateIds"]))
    flow["analysisGroups"] = [group for group in groups if group["id"] in retained]
