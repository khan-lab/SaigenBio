"""Observed shell activity and explicitly saved analysis states."""
from __future__ import annotations
import copy
import os
from pathlib import Path
import re
import shlex
from . import __version__
from .store import RecordError, entity, now, text, uid
from .runner import code_info

SECRET = re.compile(
    r"(?ix)(?:\b[\w-]*(?:password|passwd|secret|token|api[_-]?key|authorization|credential|private[_-]?key)[\w-]*\s*[=:]"
    r"|--?(?:password|passwd|token|secret|api[-_]?key|authorization|credential)\b"
    r"|\bBearer\s+\S+|://[^/\s:@]+:[^/\s@]+@"
    r"|\b(?:sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9]{12,}|AKIA[A-Z0-9]{16})"
    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----)"
)
def safe_command(command):
    if SECRET.search(command):
        return "[Command omitted: possible secret]", True
    if len(command)>20000:
        return "[Command omitted: exceeds recording limit]", True
    return command, False

def control_command(command):
    """Only skip standalone recorder invocations, not compound shell commands."""
    try:
        tokens=list(shlex.shlex(command,posix=True,punctuation_chars=";&|()<>\n"))
        if any(t in {";","&","&&","||","|","(",")",">",">>","<","<<","\n"} for t in tokens):
            return False
        words=shlex.split(command)
    except ValueError:
        return False
    if not words:return True
    while words and re.fullmatch(r"[A-Za-z_]\w*=.*",words[0]):words.pop(0)
    if not words:return False
    if words[0] in {"exit","logout"}:return True
    if Path(words[0]).name=="saigen":return True
    return len(words)>=3 and Path(words[0]).name.startswith("python") and words[1:3]==["-m","saigen"]

def background_possible(command):
    try:
        words=list(shlex.shlex(command,posix=True,punctuation_chars="&;|"))
        return "&" in words or any(w in {"bg","disown","nohup"} for w in words)
    except ValueError:
        return True

def session(flow, ident):
    try:return flow.get("sessions",{})[ident]
    except KeyError:raise RecordError("Recorded shell session not found") from None

def active(flow, ident):
    item=session(flow,ident)
    if item["status"]!="open":raise RecordError("This shell session is closed")
    return item

def resolve_state(flow, selector):
    if selector is None:
        if flow["states"]:raise RecordError("Choose a starting state with --from (a unique title or state ID)")
        return None
    exact=[n for n in flow["states"] if n["id"]==selector]
    matches=exact or [n for n in flow["states"] if n["title"]==selector]
    if len(matches)!=1:raise RecordError("Starting state is missing or ambiguous; use its state ID")
    n=matches[0]
    if n["status"] not in {"imported","completed","saved"}:
        raise RecordError("Start from imported, completed, or saved evidence")
    return n["id"]

def begin(store, parent=None, actor="Human", cwd=None, record_output=False):
    ident=uid("session")
    def change(f):
        head=resolve_state(f,parent)
        item={"id":ident,"actor":text(actor,"actor",120,True),"status":"open","paused":False,
              "startedAt":now(),"recorderVersion":__version__,"cwd":str(cwd or Path.cwd()),"ownerPid":os.getpid(),
              "head":head,"cursor":0,"commands":[],"gaps":[],"gapCursor":0,"recordOutput":record_output}
        f.setdefault("sessions",{})[ident]=item
        return {"session":copy.deepcopy(item)},None
    store.update("terminal.started",actor,change)
    return ident

def command_start(store, ident, command, cwd):
    if control_command(command):return
    cleaned,redacted=safe_command(command)
    def change(f):
        s=active(f,ident)
        if s["paused"]:return {"sessionId":ident,"paused":True},None
        for c in s["commands"]:
            if c["status"]=="running":
                c.update(status="unknown",finishedAt=now())
        item={"id":uid("cmd"),"command":cleaned,"redacted":redacted,"cwd":str(cwd),
              "startedAt":now(),"status":"running","exitCode":None,
              "backgroundPossible":background_possible(command)}
        s["commands"].append(item)
        return {"sessionId":ident,"command":copy.deepcopy(item)},None
    store.update("terminal.command_started",session(store.flow(),ident)["actor"],change)

def command_end(store, ident, exit_code, pipeline=()):
    current=session(store.flow(),ident)
    if not any(c["status"]=="running" for c in current["commands"]):return
    def change(f):
        s=active(f,ident)
        running=next((c for c in reversed(s["commands"]) if c["status"]=="running"),None)
        if running:
            running.update(status="shell-returned",finishedAt=now(),exitCode=exit_code,
                           pipelineExitCodes=list(pipeline))
        return {"sessionId":ident,"command":copy.deepcopy(running)},None
    store.update("terminal.command_returned",current["actor"],change)

def pause(store, ident, value):
    def change(f):
        s=active(f,ident)
        s["paused"]=value
        if value:s["gaps"].append({"startedAt":now(),"reason":"Recording paused"})
        elif s["gaps"] and "finishedAt" not in s["gaps"][-1]:s["gaps"][-1]["finishedAt"]=now()
        return {"sessionId":ident,"paused":value},None
    store.update("terminal.paused" if value else "terminal.resumed",session(store.flow(),ident)["actor"],change)
    return {"recording":"paused" if value else "active"}

def close(store, ident, interrupted=False, transcript=None):
    logs=[]
    if transcript and Path(transcript).is_file():logs=[store.capture(transcript,name="terminal-output.log",role="log")]
    def change(f):
        s=session(f,ident)
        for c in s["commands"]:
            if c["status"]=="running":c.update(status="unknown",finishedAt=now())
        s.update(status="interrupted" if interrupted else "closed",finishedAt=now())
        if s["gaps"] and "finishedAt" not in s["gaps"][-1]:s["gaps"][-1]["finishedAt"]=now()
        s["logArtifacts"]=[a["id"] for a in logs]
        f["artifacts"].update({a["id"]:a for a in logs})
        return {"session":copy.deepcopy(s),"artifacts":logs},None
    store.update("terminal.closed","Recorder",change)

def recover(store):
    for ident,s in store.flow().get("sessions",{}).items():
        if s["status"]!="open":continue
        try:os.kill(s["ownerPid"],0)
        except ProcessLookupError:close(store,ident,interrupted=True)
        except PermissionError:pass

def attach_run(store, ident, action_id):
    """Link observed wrapper execution without creating a duplicate shell node."""
    def change(f):
        s=active(f,ident)
        a=entity(f,"actions",action_id)
        a["sessionId"]=ident
        s.setdefault("wrappedActions",[]).append(action_id)
        return {"sessionId":ident,"actionId":action_id},None
    store.update("terminal.run_linked","Recorder",change)

def advance_after_run(store, ident, state_id):
    def change(f):
        s=active(f,ident)
        s["head"]=state_id
        return {"sessionId":ident,"stateId":state_id},None
    store.update("terminal.head_changed","Recorder",change)

def save(store, ident, title, outputs, reason="", scripts=(), source_repo=None, parent=None):
    s=active(store.flow(),ident)
    if s["paused"]:raise RecordError("Resume recording before saving a state")
    if not outputs:raise RecordError("Select at least one --output to preserve")
    # Relative selections refer to the user's current shell directory, not the recorder project.
    records=[store.capture(Path(p).expanduser(),role="output") for p in outputs]
    code=code_info(source_repo or Path.cwd())
    extras=[store.capture(Path(p).expanduser(),role="code") for p in scripts]
    code["scriptArtifacts"]=[a["id"] for a in extras]
    code["capturedAt"]=now()
    sid,aid=uid("st"),uid("shell")
    def change(f):
        s=active(f,ident)
        if s["paused"]:raise RecordError("Recording was paused while saving")
        commands=copy.deepcopy(s["commands"][s["cursor"]:])
        if any(c["status"]=="running" for c in commands):
            raise RecordError("Wait for the foreground command to return before saving")
        head=resolve_state(f,parent) if parent else s["head"]
        parents=[head] if head else []
        ps=[entity(f,"states",p) for p in parents]
        x=max((n["x"] for n in ps),default=-320)+320
        y=ps[0]["y"] if ps else 0
        while any(abs(n["x"]-x)<215 and abs(n["y"]-y)<165 for n in f["states"]):y+=210
        gaps=copy.deepcopy(s["gaps"][s["gapCursor"]:])
        activity={"sessionId":ident,"commands":commands,"gaps":gaps,
                  "association":"Commands grouped by the saver; file producers and inputs are not inferred."}
        at=now()
        ids=[r["id"] for r in records]
        manifest=list(dict.fromkeys([*(ps[0].get("manifest",[]) if ps else []),*ids]))
        n={"id":sid,"title":text(title,"title",120,True),"note":text(reason,"reason"),
           "status":"saved","origin":"terminal","writtenBy":s["actor"],"performedBy":s["actor"],
           "createdAt":at,"finishedAt":at,"x":x,"y":y,"artifactIds":ids,"manifest":manifest,
           "files":[r["name"] for r in records],"references":[],"code":code,"codeRef":code.get("commit"),
           "terminal":activity}
        f["states"].append(n)
        f["artifacts"].update({r["id"]:r for r in records+extras})
        action=None
        if parents:
            action={"id":aid,"from":parents,"to":sid,"label":f"Saved step · {len(commands)} commands",
                    "status":"saved","origin":"terminal","command":"\n".join(c["command"] for c in commands),
                    "reason":reason,"writtenBy":s["actor"],"performedBy":s["actor"],"createdAt":at,"finishedAt":at,
                    "startedAt":commands[0]["startedAt"] if commands else at,"exitCode":None,"code":code,
                    "inputArtifacts":[],"terminal":activity,
                    "methodSource":"Observed shell activity; commands and selected files grouped by the saver. Input dependencies are not inferred."}
            f["actions"].append(action)
        s.update(head=sid,cursor=len(s["commands"]),gapCursor=len(s["gaps"]))
        return {"sessionId":ident,"state":n,"action":action,"artifacts":records+extras},None
    f=store.update("terminal.saved",s["actor"],change)
    return entity(f,"states",sid)
