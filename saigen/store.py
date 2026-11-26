"""Durable project records and immutable artifact snapshots (Python standard library)."""
from __future__ import annotations
import csv
import io
import copy
import hashlib
import json
import mimetypes
import os
import re
from pathlib import Path
import sqlite3
import tempfile
from datetime import datetime, timezone

# Re-export record helpers for compatibility with existing integrations.
from .records import (ID, TERMINAL, RecordError, Conflict, now, uid, entity,
                      text, names, coordinates, plan_removal_error, validate)
from .analysis_groups import remove_missing_members
from .bookmarks import remove_deleted
from .overview_layout import edit_overview
from .lineage import run_lineage

def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()
def table_preview(path, filename):
    if Path(filename).suffix.lower() not in {".csv",".tsv"}:
        return None
    try:
        with Path(path).open("rb") as handle:
            sample=handle.read(65536)
        reader=csv.reader(io.StringIO(sample.decode("utf-8-sig")), delimiter="\t" if filename.lower().endswith(".tsv") else ",")
        rows=[]
        for row in reader:
            rows.append([cell[:160] for cell in row[:6]])
            if len(rows)==6: break
        if len(rows)>1:
            return {"columns":rows[0],"rows":rows[1:],"truncated":True}
    except (UnicodeError,csv.Error,OSError):
        pass
    return None

class Store:
    def __init__(self, project):
        self.root = Path(project).expanduser().resolve()
        self.home = self.root / ".saigen"
        self.db = self.home / "project.sqlite"
    def connect(self):
        if not self.db.is_file():
            raise RecordError("Project is not initialized. Run: python3 -m saigen --project PATH init")
        db = sqlite3.connect(self.db, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        return db
    def init(self, name=None):
        self.root.mkdir(parents=True, exist_ok=True)
        self.home.mkdir(exist_ok=True)
        (self.home / "objects").mkdir(exist_ok=True)
        (self.home / "runs").mkdir(exist_ok=True)
        with sqlite3.connect(self.db, timeout=15) as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("CREATE TABLE IF NOT EXISTS project (id INTEGER PRIMARY KEY CHECK(id=1), data TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS events (revision INTEGER PRIMARY KEY, at TEXT NOT NULL, actor TEXT NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL, inverse TEXT)")
            flow = {"schemaVersion":1,"project":name or self.root.name,"revision":0,"states":[],"actions":[],"artifacts":{},"createdAt":now()}
            db.execute("INSERT OR IGNORE INTO project VALUES (1,?)", (json.dumps(flow),))
        return self.flow()
    def flow(self):
        with self.connect() as db:
            flow = json.loads(db.execute("SELECT data FROM project WHERE id=1").fetchone()[0])
        flow["revisions"] = []
        return flow
    def events(self):
        with self.connect() as db:
            return [{**dict(r), "payload":json.loads(r["payload"]), "undoable":bool(r["inverse"])} for r in db.execute("SELECT revision,at,actor,kind,payload,inverse FROM events ORDER BY revision")]
    def update(self, kind, actor, change, expected=None):
        text(actor, "actor", 120, True)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            flow = json.loads(db.execute("SELECT data FROM project WHERE id=1").fetchone()[0])
            if expected is not None and (type(expected) is not int or flow["revision"] != expected):
                raise Conflict("The project changed. Review the latest state and save again.")
            prior_ids = {n['id'] for n in flow['states']}
            explained_ids = {sid for e in flow.get('explanations', {}).values()
                             for sid in e['states'] + ([e['replacementStateId']] if e.get('replacementStateId') else [])
                             + [r['id'] for r in e.get('evidence', []) if r['type'] == 'state']}
            payload, inverse = change(flow)
            current_ids = {n['id'] for n in flow['states']}
            if kind != 'flow.undo' and (current_ids - prior_ids) & explained_ids:
                raise RecordError('State ID belongs to existing explanation history; use a new ID')
            remove_missing_members(flow, prior_ids - current_ids)
            remove_deleted(db, prior_ids - current_ids)
            validate(flow)
            flow["revision"] += 1
            at = now()
            db.execute("INSERT INTO events VALUES (?,?,?,?,?,?)", (flow["revision"],at,actor,kind,json.dumps(payload),json.dumps(inverse) if inverse else None))
            db.execute("UPDATE project SET data=? WHERE id=1", (json.dumps(flow),))
        return self.flow()

    def capture(self, path, name=None, role="output", preserve=True):
        path = Path(path).expanduser().resolve(strict=True)
        if not path.is_file():
            raise RecordError(f"Not a regular file: {path}")
        before = path.stat()
        h = hashlib.sha256()
        tmp = None
        try:
            if preserve:
                fd, tmp = tempfile.mkstemp(dir=self.home / "objects", prefix=".capture-")
                target = os.fdopen(fd, "wb")
            else:
                target = None
            with path.open("rb") as source:
                try:
                    for chunk in iter(lambda: source.read(1024 * 1024), b""):
                        h.update(chunk)
                        if target: target.write(chunk)
                finally:
                    if target: target.close()
            after = path.stat()
            if (before.st_size,before.st_mtime_ns,before.st_ino) != (after.st_size,after.st_mtime_ns,after.st_ino):
                raise RecordError(f"File changed while being recorded: {path}")
            sha = h.hexdigest()
            if preserve:
                dest = self.home / "objects" / sha
                if dest.exists():
                    if digest(dest) != sha: raise RecordError("An existing artifact snapshot is damaged")
                    os.unlink(tmp)
                else:
                    os.chmod(tmp, 0o444)
                    os.replace(tmp, dest)
                tmp = None
            filename = name or path.name
            mime = mimetypes.guess_type(filename)[0] or ("text/plain" if path.suffix in {".vcf",".tsv",".log",".md",".py",".R",".sh",".lock"} else "application/octet-stream")
            preview = table_preview(dest, filename) if preserve else None
            return {"tablePreview":preview,"id":uid("ar"),"name":filename,"sha256":sha,"size":after.st_size,"mime":mime,"role":role,"sourcePath":str(path),"storage":"preserved" if preserve else "reference","capturedAt":now()}
        finally:
            if tmp and Path(tmp).exists(): os.unlink(tmp)
    def artifact_path(self, artifact, verify=True):
        sha = artifact["sha256"]
        if not re.fullmatch(r"[0-9a-f]{64}", sha):
            raise RecordError("Invalid artifact hash")
        path = self.home / "objects" / sha if artifact["storage"] == "preserved" else Path(artifact["sourcePath"])
        if not path.is_file():
            raise RecordError("The recorded file is missing")
        if verify and digest(path) != sha:
            raise RecordError("The recorded file has changed")
        return path
    def artifact(self, ident):
        try: return self.flow()["artifacts"][ident]
        except KeyError: raise RecordError("Unknown artifact") from None
    def snapshot(self, title, files, actor="AI agent", note="", ident=None, references=(), code=None):
        records = [self.capture(p, role="input") for p in files]
        records += [self.capture(p, role="input", preserve=False) for p in references]
        ident = ident or uid("st")
        def change(f):
            if any(n["id"] == ident for n in f["states"]): raise RecordError("State ID already exists")
            n = {"id":ident,"title":text(title,"title",120,True),"note":text(note,"note"),"x":0,"y":len(f["states"])*190,"status":"imported","origin":"imported","writtenBy":actor,"performedBy":None,"createdAt":now(),"codeRef":(code or {}).get("commit"),"code":code or {},"artifactIds":[a["id"] for a in records],"manifest":[a["id"] for a in records],"files":[a["name"] for a in records],"references":[]}
            f["states"].append(n)
            f["artifacts"].update({a["id"]:a for a in records})
            return {"state":n,"artifacts":records,"execution":"Unknown; existing files imported"}, None
        flow = self.update("snapshot.imported",actor,change)
        return entity(flow,"states",ident)

    def plan(self, title, parents, expected, outputs=(), actor="AI agent", ident=None, *, details="", requires=""):
        ident = ident or uid("st")
        def change(f):
            if any(n["id"] == ident for n in f["states"]):
                raise RecordError("State ID already exists")
            ps = [entity(f, "states", i) for i in parents]
            if not ps:
                raise RecordError("A planned result needs an input state")
            x = max(n["x"] for n in ps) + 320
            y = ps[0]["y"]
            while any(abs(n["x"]-x)<215 and abs(n["y"]-y)<165 for n in f["states"]):
                y += 210
            n = {"id":ident, "title":text(title,"title",120,True),
                 "note":"", "expectedSummary":text(expected,"expected output",20000,True),
                 "planDetails":text(details,"plan details"), "planRequires":text(requires,"prerequisite"),
                 "planParents":list(parents), "expectedFiles":names(list(outputs)),
                 "status":"planned", "origin":"agent-plan", "writtenBy":actor,
                 "performedBy":None, "createdAt":now(), "x":x, "y":y,
                 "artifactIds":[], "manifest":[], "files":[], "references":[]}
            f["states"].append(n)
            return {"state":n}, None
        return entity(self.update("plan.proposed",actor,change),"states",ident)

    def begin(self, title, parents, command, actor, reason, outputs, inputs, code, environment, ident=None, label=None, planned=None, expected="", acquisition=False,
              *, explicit_artifacts=(), ask_lineage=True, approved=False):
        ident = planned or ident or uid("st")
        aid = uid("run")
        def change(f):
            existing = next((n for n in f["states"] if n["id"]==ident),None)
            declared_parents = parents
            if acquisition:
                resolved_parents, file_bindings = declared_parents, []
            else:
                resolved_parents, file_bindings = run_lineage(f, declared_parents, explicit_artifacts,
                                                              ask=ask_lineage, approved=approved)
            if planned:
                if not existing or existing.get("origin")!="agent-plan" or existing["status"]!="planned":
                    raise RecordError("Select an unexecuted agent plan")
                if not declared_parents and set(resolved_parents)==set(existing["planParents"]):
                    resolved_parents=existing["planParents"]
                if resolved_parents != existing["planParents"]:
                    raise RecordError("Run inputs must match the planned parents")
            elif existing:
                raise RecordError("State ID already exists")
            ps = [entity(f,"states",i) for i in resolved_parents]
            if any(n.get("reconstruction",{}).get("review")=="draft" for n in ps):raise RecordError("Accept reconstruction before running from its states")
            if not ps and not acquisition: raise RecordError("A run needs at least one parent")
            if acquisition and ps: raise RecordError("Acquisition must be a root state")
            if any(n["status"] not in {"imported","completed","saved"} for n in ps):
                raise RecordError("Use an imported or completed parent state")
            x = max((n["x"] for n in ps),default=-320)+320
            y = ps[0]["y"] if ps else 0
            while any(abs(n["x"]-x)<215 and abs(n["y"]-y)<165 for n in f["states"]): y += 210
            inherited = list(dict.fromkeys(a for n in ps for a in n.get("manifest",[])))
            at = now()
            n = {"id":ident,"title":text(title,"title",120,True),"note":text(reason,"reason"),"x":x,"y":y,"status":"running","origin":"recorded","writtenBy":actor,"performedBy":actor,"createdAt":at,"codeRef":code.get("commit"),"code":code,"artifactIds":[],"manifest":inherited,"files":[],"expectedFiles":outputs,"references":[]}
            a = {"id":aid,"from":resolved_parents,"to":ident,"label":text(label or Path(command[0]).name,"label",160,True),"command":"","argvTemplate":command,"reason":reason,"reasonSource":"agent-stated" if actor!="Human" else "human-stated","status":"running","origin":"recorded","writtenBy":actor,"performedBy":actor,"startedAt":at,"heartbeatAt":at,"exitCode":None,"runnerPid":os.getpid(),"inputArtifacts":[i["id"] for i in inputs],"code":code,"environment":environment,"methodSource":"Observed by the SaigenBio execution wrapper."}
            a["acquisition"] = acquisition
            a["fileInputBindings"] = file_bindings
            n["expectedSummary"] = expected or (existing.get("expectedSummary","") if existing else "")
            if existing:
                n["x"], n["y"] = existing["x"], existing["y"]
                n["plan"] = {k:copy.deepcopy(existing[k]) for k in
                             ("title","expectedSummary","planDetails","planRequires","note","expectedFiles","planParents","createdAt","writtenBy","origin") if k in existing}
                f["states"][f["states"].index(existing)] = n
            else:
                f["states"].append(n)
            f["actions"].append(a)
            f["artifacts"].update({i["id"]:i for i in inputs})
            return {"state":n,"action":a,"inputs":inputs}, None
        self.update("run.started", actor, change)
        return aid, ident
    def describe_run(self, aid, argv, cwd):
        import shlex
        def change(f):
            a=entity(f,"actions",aid)
            if a["status"]!="running": raise RecordError("Run is not active")
            a.update(argv=argv,command=shlex.join(argv),cwd=str(cwd))
            return {"action":copy.deepcopy(a)}, None
        return self.update("run.command", "Recorder", change)
    def heartbeat(self, aid):
        # Heartbeats update liveness only; they do not create scientific-history events.
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            f=json.loads(db.execute("SELECT data FROM project WHERE id=1").fetchone()[0])
            a=entity(f,"actions",aid)
            if a["status"]=="running":
                a["heartbeatAt"]=now()
                db.execute("UPDATE project SET data=? WHERE id=1",(json.dumps(f),))
    def finish(self, aid, status, exit_code, outputs, logs, error=None):
        if status not in TERMINAL: raise RecordError("Invalid final status")
        def change(f):
            a=entity(f,"actions",aid)
            if a["status"] not in {"running","unknown"}: raise RecordError("Run already finished")
            n=entity(f,"states",a["to"])
            a.update(status=status,exitCode=exit_code,finishedAt=now(),error=error,logs=[r["id"] for r in logs])
            n.update(status=status,artifactIds=[r["id"] for r in outputs],files=[r["name"] for r in outputs],finishedAt=a["finishedAt"])
            n["manifest"]=list(dict.fromkeys(n.get("manifest",[])+n["artifactIds"]))
            if status=="completed": n.pop("expectedFiles",None)
            f["artifacts"].update({r["id"]:r for r in outputs+logs})
            return {"action":copy.deepcopy(a),"state":copy.deepcopy(n),"artifacts":outputs+logs}, None
        return self.update("run."+status,"Recorder",change)
    def recover(self, seconds=30):
        from . import sessions
        sessions.recover(self)
        # Never infer successful completion from a missing recorder.
        cutoff=datetime.now(timezone.utc).timestamp()-seconds
        stale=[a["id"] for a in self.flow()["actions"] if a["status"]=="running" and datetime.fromisoformat(a["heartbeatAt"]).timestamp()<cutoff]
        if not stale: return
        def change(f):
            recovered=[]
            for aid in stale:
                a=entity(f,"actions",aid)
                if a["status"]!="running" or datetime.fromisoformat(a["heartbeatAt"]).timestamp()>=cutoff: continue
                a.update(status="unknown",error="Recorder heartbeat was lost. Completion is unknown.")
                entity(f,"states",a["to"])["status"]="unknown"
                recovered.append(aid)
            return {"actions":recovered,"reason":"Recorder heartbeat lost"},None
        self.update("run.contact_lost","Recorder",change)

    def _operation(self, f, op, actor, internal=False):
        kind=op.get("op")
        if kind in {"archive_states", "restore_archived_states"}:
            from .state_archive import edit_archive
            return edit_archive(f, op, actor, internal)
        if kind == "edit_overview":
            return edit_overview(f, op, internal)
        ident=op.get("id")
        if not isinstance(ident,str) or not ID.fullmatch(ident): raise RecordError("Invalid record ID")
        group="actions" if "action" in str(kind) else "states"
        if kind in {"edit_state","edit_action"}:
            item=entity(f,group,ident)
            changes=op.get("changes")
            if not isinstance(changes,dict) or not changes: raise RecordError("No changes supplied")
            allowed={"title","note","x","y","references"} if group=="states" else {"label","annotation"}
            if item["origin"]=="manual" and item["status"]=="planned":
                allowed |= {"expectedFiles","expectedSummary","planDetails","planRequires"} if group=="states" else {"command","reason"}
            if not set(changes)<=allowed: raise RecordError("Execution facts cannot be edited")
            for key,value in changes.items():
                if key in {"x","y"}: coordinates({key:value})
                elif key in {"references","expectedFiles"}: names(value)
                else: text(value,key,120 if key=="title" else 20000,key in {"title","label"})
            expected=op.get("expected",{})
            if any(item.get(k)!=v for k,v in expected.items()): raise Conflict("This record changed after the edit; Undo would overwrite newer work.")
            previous={key:copy.deepcopy(item.get(key,[] if key in {"references","expectedFiles"} else "")) for key in changes}
            item.update(changes)
            item["lastEditedBy"]=actor;item["updatedAt"]=now()
            return {"op":kind,"id":ident,"changes":previous,"expected":copy.deepcopy(changes)}
        if kind=="add_state":
            if any(n["id"]==ident for n in f["states"]): raise RecordError("State ID already exists")
            value=op.get("value",{})
            n={"id":ident,"title":text(value.get("title",""),"title",120,True),"note":text(value.get("note",""),"note"),"x":value.get("x",0),"y":value.get("y",0),"files":[],"artifactIds":[],"manifest":[],"expectedFiles":names(value.get("expectedFiles",[])),"references":[],"status":"planned","origin":"manual","writtenBy":actor,"performedBy":None,"createdAt":now(),"codeRef":None}
            for key in ("expectedSummary","planDetails","planRequires"):
                n[key]=text(value.get(key,""),key)
            coordinates(n);f["states"].append(n)
            return {"op":"delete_state","id":ident,"expected":copy.deepcopy(n)}
        if kind=="add_action":
            if any(a["id"]==ident for a in f["actions"]): raise RecordError("Action ID already exists")
            value=op.get("value",{})
            target=entity(f,"states",value.get("to"))
            if target["origin"]!="manual" or target["status"]!="planned": raise RecordError("Connect to a new planned state; an executed state's inputs are preserved.")
            parents=value.get("from",[])
            if not isinstance(parents,list) or not parents or not all(isinstance(x,str) for x in parents): raise RecordError("Invalid parents")
            a={"id":ident,"from":parents,"to":target["id"],"label":text(value.get("label",""),"label",160,True),"command":text(value.get("command",""),"command"),"reason":text(value.get("reason",""),"reason"),"status":"planned","origin":"manual","writtenBy":actor,"performedBy":None,"createdAt":now(),"methodSource":"Manually supplied plan; no execution recorded."}
            f["actions"].append(a)
            return {"op":"delete_action","id":ident,"expected":copy.deepcopy(a)}
        if kind in {"delete_state","delete_action"}:
            item=entity(f,group,ident)
            if group == "states":
                error = plan_removal_error(f, ident)
                if error: raise RecordError(error)
            elif item["origin"] != "manual" or item["status"] != "planned":
                raise RecordError("Recorded execution history cannot be deleted")
            if "expected" in op:
                clean=lambda v:{k:x for k,x in v.items() if k not in {"updatedAt","lastEditedBy"}}
                if clean(item)!=clean(op["expected"]): raise Conflict("The record has changed since it was added")
            related=[]
            if group=="states":
                related=[a for a in f["actions"] if a["to"]==ident or ident in a["from"]]
                if any(a["origin"]!="manual" for a in related): raise RecordError("This state is used by a recorded execution")
                f["actions"]=[a for a in f["actions"] if a not in related]
            f[group].remove(item)
            return {"op":"restore_action" if group=="actions" else "restore_state","id":ident,"value":copy.deepcopy(item),"related":copy.deepcopy(related)}
        if kind in {"restore_state","restore_action"} and internal:
            if any(n["id"]==ident for n in f[group]): raise Conflict("The ID has been reused")
            value = op["value"]
            if group == "states":
                parents = value.get("planParents", []) + value.get("plan", {}).get("planParents", [])
                if any(not any(n["id"] == parent for n in f["states"]) for parent in parents):
                    raise Conflict("An input was removed; this plan can no longer be restored")
            restored_ids = {n["id"] for n in f["states"]} | ({ident} if group == "states" else set())
            actions = op.get("related", []) if group == "states" else [value]
            if any(a["to"] not in restored_ids or any(i not in restored_ids for i in a["from"]) for a in actions):
                raise Conflict("A connected state was removed; this connection can no longer be restored")
            f[group].append(copy.deepcopy(value))
            for a in op.get("related",[]):
                if any(x["id"]==a["id"] for x in f["actions"]): raise Conflict("An action ID has been reused")
                f["actions"].append(copy.deepcopy(a))
            return {"op":"delete_action" if group=="actions" else "delete_state","id":ident}
        raise RecordError("Unsupported edit")
    def edit(self, ops, expected, actor="Human"):
        if not isinstance(ops,list) or not ops: raise RecordError("Expected at least one operation")
        def change(f):
            # A canvas arrangement can move every state in one undoable revision.
            # Keep the ordinary batch limit for all other kinds of edit.
            if len(ops) > 100:
                ids = set()
                for op in ops:
                    if (not isinstance(op, dict) or op.get("op") != "edit_state"
                            or not isinstance(op.get("id"), str) or op["id"] in ids
                            or not isinstance(op.get("changes"), dict)
                            or set(op["changes"]) != {"x", "y"}):
                        raise RecordError("Expected 1 to 100 operations or one position edit per state")
                    ids.add(op["id"])
            inverse=[]
            for op in ops:
                if not isinstance(op,dict): raise RecordError("Invalid operation")
                inverse.insert(0,self._operation(f,op,actor))
            return {"operations":ops},inverse
        return self.update("flow.edited",actor,change,expected)
    def undo(self, revision, expected, actor="Human"):
        with self.connect() as db:
            row=db.execute("SELECT inverse FROM events WHERE revision=?",(revision,)).fetchone()
        if not row or not row[0]: raise RecordError("This event cannot be undone")
        inverse=json.loads(row[0])
        def change(f):
            redo=[]
            for op in inverse: redo.insert(0,self._operation(f,op,actor,True))
            return {"undoOf":revision,"operations":inverse},redo
        return self.update("flow.undo",actor,change,expected)
    def export(self, destination):
        with self.connect() as db:
            db.execute("BEGIN")
            flow=json.loads(db.execute("SELECT data FROM project WHERE id=1").fetchone()[0])
            events=[{**dict(r),"payload":json.loads(r["payload"])} for r in db.execute("SELECT revision,at,actor,kind,payload FROM events ORDER BY revision")]
        data={"schemaVersion":1,"flow":flow,"events":events,"artifactsDirectory":"Copy .saigen/objects alongside the export to preserve artifact bodies."}
        destination=Path(destination)
        destination.write_text(json.dumps(data,indent=2)+"\n")
        return destination
