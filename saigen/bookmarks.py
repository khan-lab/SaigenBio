"""Project-local Canvas bookmarks stored alongside the graph."""
import json

from .records import RecordError


def _exists(db):
    return db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='canvas_bookmarks'").fetchone() is not None


def _ids(db):
    return [row[0] for row in db.execute("SELECT state_id FROM canvas_bookmarks ORDER BY state_id")]


def canvas_status(store):
    with store.connect() as db:
        db.execute("BEGIN")
        revision = json.loads(db.execute("SELECT data FROM project WHERE id=1").fetchone()[0])["revision"]
        return {"revision": revision, "bookmarks": _ids(db) if _exists(db) else []}


def set_saved(store, state_id, saved):
    if not isinstance(state_id, str) or type(saved) is not bool:
        raise RecordError("A state ID and bookmark preference are required")
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        flow = json.loads(db.execute("SELECT data FROM project WHERE id=1").fetchone()[0])
        if not any(state["id"] == state_id for state in flow["states"]):
            raise RecordError("Choose a state on the Canvas")
        db.execute("CREATE TABLE IF NOT EXISTS canvas_bookmarks (state_id TEXT PRIMARY KEY)")
        if saved:
            db.execute("INSERT OR IGNORE INTO canvas_bookmarks VALUES (?)", (state_id,))
        else:
            db.execute("DELETE FROM canvas_bookmarks WHERE state_id=?", (state_id,))
        return _ids(db)


def remove_deleted(db, deleted):
    if deleted and _exists(db):
        db.executemany("DELETE FROM canvas_bookmarks WHERE state_id=?", ((state_id,) for state_id in deleted))
