"""Run an explicitly supplied command and record observed process facts."""
from __future__ import annotations
import json
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from . import __version__
from .store import Store, RecordError, digest, now, entity, text

def code_info(folder):
    folder=Path(folder).resolve()
    def git(*args):
        try:
            p=subprocess.run(["git","-C",str(folder),*args],capture_output=True,text=True,timeout=10)
            return p.stdout.strip() if p.returncode==0 else None
        except (OSError,subprocess.TimeoutExpired):
            return None
    root=git("rev-parse","--show-toplevel")
    if not root: return {"commit":None,"repository":None,"dirty":None}
    status=git("status","--porcelain","--untracked-files=normal")
    return {"commit":git("rev-parse","HEAD"),"repository":root,"dirty":bool(status),"status":status,"trackedDiff":git("diff","HEAD","--binary")}

def local_output(work, name):
    text=Path(name)
    if text.is_absolute() or not text.parts or ".." in text.parts:
        raise RecordError("Output names must be relative to the isolated run directory")
    target=(work/text).resolve()
    if not target.is_relative_to(work.resolve()): raise RecordError("Output leaves the run directory")
    return target

def run(store, parents, title, command, *, inputs=(), outputs=(), actor="AI agent",
        reason="", label=None, ident=None, stdout_name=None, source_repo=None,
        scripts=(), environment_files=(), tool_versions=(), planned=None, expected="", acquisition=False, source_urls=(), explanation="", script_excerpts=()):
    if not command or not all(isinstance(v,str) and v for v in command):
        raise RecordError("Supply a command after --")
    if any(n['id'] in parents and n.get('reconstruction',{}).get('review')=='draft' for n in store.flow()['states']):
        raise RecordError("Review and accept the reconstruction before using its states in a run")
    outputs=list(outputs)
    if stdout_name and stdout_name not in outputs: outputs.append(stdout_name)
    for output in outputs: local_output(Path("/placeholder"),output)
    input_records=[]
    for spec in inputs:
        if str(spec).startswith("artifact:"):
            item=store.artifact(str(spec).split(":",1)[1])
            store.artifact_path(item)
        else:
            path=Path(spec).expanduser()
            item=store.capture(path if path.is_absolute() else store.root/path,role="input")
        input_records.append(item)
    for argument in command:
        for index in re.findall(r"\{input:(\d+)\}",argument):
            if int(index)>=len(input_records): raise RecordError("Unresolved input placeholder")
    code=code_info(source_repo or store.root)
    extra_records=[]
    explicit=list(scripts)
    selections=[]
    explanation=text(explanation,"explanation",4000)
    for spec in script_excerpts:
        try:
            filename, first, last = spec.rsplit(":", 2)
            first, last = int(first), int(last)
        except (ValueError, AttributeError):
            raise RecordError("Script excerpt must be PATH:START:END") from None
        if first < 1 or last < first or last-first >= 40:
            raise RecordError("Select 1–40 script lines using positive line numbers")
        path=Path(filename).expanduser()
        path=(path if path.is_absolute() else store.root/path).resolve()
        explicit.append(str(path))
        selections.append((path,first,last))
    for argument in command:
        path=Path(argument)
        candidate=path if path.is_absolute() else store.root/path
        if path.suffix.lower() in {".py",".r",".sh",".pl",".jl",".ipynb"} and candidate.is_file():
            explicit.append(str(candidate))
    seen_scripts=set()
    for spec in explicit:
        p=Path(spec).expanduser()
        p=(p if p.is_absolute() else store.root/p).resolve()
        if p not in seen_scripts:
            extra_records.append(store.capture(p,role="code"))
            seen_scripts.add(p)
    for spec in environment_files:
        p=Path(spec).expanduser()
        extra_records.append(store.capture(p if p.is_absolute() else store.root/p,role="environment"))
    executable=shutil.which(command[0])
    environment={"platform":platform.platform(),"recorderPython":sys.version,"recorderVersion":__version__,"executable":executable,"executableSha256":digest(executable) if executable and Path(executable).is_file() else None,"declaredToolVersions":list(tool_versions),"capturedFiles":[r["id"] for r in extra_records]}
    environment["declaredSourceURLs"]=list(source_urls)
    code["scriptArtifacts"]=[r["id"] for r in extra_records if r["role"]=="code"]
    if explanation or selections:
        excerpts=[]
        for path,first,last in selections:
            artifact=next(r for r in extra_records if r["role"]=="code" and Path(r["sourcePath"])==path)
            try:
                lines=store.artifact_path(artifact).read_text(encoding="utf-8").splitlines()
            except UnicodeError:
                raise RecordError("Script excerpts require UTF-8 text") from None
            if last > len(lines):
                raise RecordError("Script excerpt extends beyond the preserved script")
            excerpt=text("\n".join(lines[first-1:last]),"script excerpt",8000)
            excerpts.append({"artifactId":artifact["id"],"start":first,"end":last,"text":excerpt})
        code["explanation"]={"summary":explanation,"recordedBy":actor,"source":"author-stated","excerpts":excerpts}
    session_id=os.environ.get("SAIGEN_SESSION")
    if session_id:
        from . import sessions
        if Path(os.environ.get("SAIGEN_PROJECT","")).resolve()!=store.root:
            session_id=None
        else:
            sessions.active(store.flow(),session_id)
    aid,sid=store.begin(title,list(parents),list(command),actor,reason,outputs,input_records+extra_records,code,environment,ident,label,planned,expected,acquisition)
    if session_id:sessions.attach_run(store,session_id,aid)
    work=store.home/"runs"/aid/"work"
    work.mkdir(parents=True)
    logs=work.parent/"logs"
    logs.mkdir()
    argv=[]
    for argument in command:
        value=argument.replace("{project}",str(store.root)).replace("{run}",str(work))
        for index,item in enumerate(input_records):
            value=value.replace("{input:"+str(index)+"}",str(store.artifact_path(item,verify=False)))
        if "{input:" in value: raise RecordError("Unresolved input placeholder")
        argv.append(value)
    store.describe_run(aid,argv,work)
    stop=threading.Event()
    def beat():
        while not stop.wait(2):
            try: store.heartbeat(aid)
            except Exception: pass  # Liveness failure must not invent a result.
    worker=threading.Thread(target=beat,daemon=True)
    worker.start()
    proc=None
    cancelled=False
    exit_code=None
    error=None
    old_signal=None
    on_main=threading.current_thread() is threading.main_thread()
    if on_main:
        old_signal=signal.getsignal(signal.SIGTERM)
        def interrupt(signum,frame): raise KeyboardInterrupt
        signal.signal(signal.SIGTERM,interrupt)
    out_path=local_output(work,stdout_name) if stdout_name else logs/"stdout.log"
    err_path=logs/"stderr.log"
    out_path.parent.mkdir(parents=True,exist_ok=True)
    try:
        with out_path.open("wb") as stdout,err_path.open("wb") as stderr:
            try:
                proc=subprocess.Popen(argv,cwd=work,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,start_new_session=True)
                exit_code=proc.wait()
            except KeyboardInterrupt:
                cancelled=True
                if proc and proc.poll() is None:
                    os.killpg(proc.pid,signal.SIGTERM)
                    try: exit_code=proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        os.killpg(proc.pid,signal.SIGKILL);exit_code=proc.wait()
                error="Cancelled by the caller"
            except OSError as exc:
                error=str(exc)
        output_records=[]
        missing=[]
        for name in outputs:
            try:
                path=local_output(work,name)
                if path.is_file(): output_records.append(store.capture(path,name=name))
                else: missing.append(name)
            except (OSError,RecordError) as exc: missing.append(f"{name}: {exc}")
        if missing: error=(error+"; " if error else "")+"Declared outputs missing or invalid: "+", ".join(missing)
        status="cancelled" if cancelled else "completed" if exit_code==0 and not error else "failed"
        log_records=[]
        for path,name in ((out_path,"stdout.log"),(err_path,"stderr.log")):
            if path.is_file(): log_records.append(store.capture(path,name=name,role="log"))
        store.finish(aid,status,exit_code,output_records,log_records,error)
        if session_id and status=="completed":sessions.advance_after_run(store,session_id,sid)
        return {"action":aid,"state":sid,"status":status,"exitCode":exit_code,"error":error,"workdir":str(work)}
    finally:
        stop.set();worker.join(timeout=3)
        if on_main: signal.signal(signal.SIGTERM,old_signal)
