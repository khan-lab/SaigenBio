"""Archive visibility for recorded states, independent of execution status."""
from .records import Conflict, RecordError, entity, now


def can_archive(state):
    return (state["status"] in {"completed", "failed", "imported", "saved"}
            and state.get("reconstruction", {}).get("review") != "draft")


def edit_archive(flow, op, actor, internal=False):
    ids = op.get("stateIds")
    if (not isinstance(ids, list) or not ids or any(not isinstance(i, str) for i in ids)
            or len(ids) != len(set(ids))):
        raise RecordError("Select one or more distinct states")
    archived = op["op"] == "archive_states"
    states = [entity(flow, "states", ident) for ident in ids]
    archive = flow.get("stateArchives", {})
    if any((ident in archive) == archived for ident in ids):
        raise Conflict("The selected states' archive status has changed")
    if internal and "entries" in op and any(archive[ident] != op["entries"][ident] for ident in ids):
        raise Conflict("The selected states have been archived again")
    if archived:
        if any(not can_archive(state) for state in states):
            raise RecordError("Deselect states that are not eligible for archiving")
        entries = op.get("previous") if internal else None
        if entries is None:
            entries = {ident: {"at": now(), "actor": actor} for ident in ids}
        archive.update(entries)
        flow["stateArchives"] = archive
        return {"op": "restore_archived_states", "stateIds": ids, "entries": entries}
    previous = {ident: archive.pop(ident) for ident in ids}
    if not archive:
        flow.pop("stateArchives", None)
    return {"op": "archive_states", "stateIds": ids, "previous": previous}


def set_archived(store, state_id, archived, revision, actor):
    kind = "archive_states" if archived else "restore_archived_states"
    return store.edit([{"op": kind, "stateIds": [state_id]}], revision, actor)
