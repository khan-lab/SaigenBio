"""SaigenBio CLI; also available as python3 -m saigen."""
import argparse
import json
import os
from pathlib import Path
import sys
from . import __version__
from .store import Store
from .records import RecordError
from .runner import run, code_info
from .server import serve
from . import sessions

def main():
    parser=argparse.ArgumentParser(prog="saigen",description="Record analysis states and view their history.")
    parser.add_argument("--version",action="version",version="%(prog)s "+__version__)
    parser.add_argument("--project",default=os.environ.get("SAIGEN_PROJECT","."))
    parser.add_argument("--actor",default=None,help="Declared identity; not authenticated")
    sub=parser.add_subparsers(dest="command",required=True,metavar="{verify,workflow,pipeline,reconstruct,groups,explain,story,annotate,acquire,setup,init,snapshot,plan,remove-plan,run,serve,flow,history,recover,export,start,save,pause,resume,status,commands}")
    def command(name,**kwargs):
        p=sub.add_parser(name,**kwargs)
        p.add_argument("--project",default=argparse.SUPPRESS)
        p.add_argument("--actor",default=argparse.SUPPRESS)
        return p
    from .workflows.cli import register as register_workflows
    register_workflows(command)
    from .workflows.export_cli import register as register_pipeline
    register_pipeline(command)
    from .verification_cli import register as register_verification
    register_verification(command)
    p=command("setup",help="Prepare a workspace for an AI agent")
    p.add_argument("--workspace",required=True)
    p.add_argument("--agent",choices=["codex","claude","opencode","antigravity"],action="append",required=True)
    p.add_argument("--analysis-project",required=True)
    p.add_argument("--input",action="append",default=[])
    p.add_argument("--viewer",default=None)
    p.add_argument("--ui-development",choices=["ask","allow"],help="Permission for routine local SaigenBio UI source changes (default: ask for new workspaces)")
    p.add_argument("--permissions",choices=["ask","flexible"],default=None,help="Agent workflow preference; does not grant host access")
    p=command("annotate");p.add_argument("--state",required=True);p.add_argument("--note",required=True)
    p=command("init",help="Initialize a project; interview in a terminal, flags for automation")
    p.add_argument("--existing-project",help="Directory of an existing analysis to reconstruct")
    p.add_argument("--history-file",action="append",default=[],help="Conversation or notes file; repeat for several")
    p.add_argument("--name")
    p.add_argument("--agent",choices=["codex","claude","opencode","antigravity"],action="append",help="Set up an agent; repeat for several")
    p.add_argument("--port",type=int,help="Save the viewer port (default: 8767)")
    p.add_argument("--ui-development",choices=["ask","allow"],help="Permission for routine local SaigenBio UI source changes (default: ask for new workspaces)")
    p.add_argument("--permissions",choices=["ask","flexible"],help="Agent workflow preference; does not grant host access")
    p.add_argument("--non-interactive",action="store_true",help="Use flags and defaults without prompting")
    start=p.add_mutually_exclusive_group()
    start.add_argument("--start-viewer",dest="start_viewer",action="store_true",default=None)
    start.add_argument("--no-start-viewer",dest="start_viewer",action="store_false")
    p=command("reconstruct",help="Propose and review an evidence-linked historical reconstruction")
    p.add_argument("operation",choices=["sources","propose","show","accept","reject"])
    p.add_argument("--agent",choices=["codex","claude","opencode","antigravity"],
                   help="Agent whose local session metadata to check with reconstruct sources")
    p.add_argument("--file",help="Proposal JSON file")
    p.add_argument("--id")
    p.add_argument("--revision",type=int)
    p.add_argument("--state",help="Review one reconstruction state")
    p.add_argument("--connection",help="Review one reconstruction relationship")
    p.add_argument("--evidence",help="Review one additional-evidence item")
    p.add_argument("--reason",default="",help="Reason for the review decision")
    p=command("groups",help="Show or save analysis groups for the Canvas")
    grouping=p.add_subparsers(dest="operation",required=True)
    show_groups=grouping.add_parser("show",help="List saved groups and the project revision")
    save_groups=grouping.add_parser("save",help="Replace the saved groups with an agreed JSON list")
    for operation in (show_groups,save_groups):
        operation.add_argument("--project",default=argparse.SUPPRESS)
        operation.add_argument("--actor",default=argparse.SUPPRESS)
    save_groups.add_argument("--file",required=True,help="JSON array of groups")
    save_groups.add_argument("--revision",required=True,type=int)
    p=command("explain",help="Append an attributed statement, decision, correction or replacement link")
    p.add_argument("--file",required=True,help="Explanation JSON document")
    p.add_argument("--revision",type=int,required=True)
    p=command("story",help="Read What, Why, Who and When evidence for a current or archived state")
    p.add_argument("state")
    p=command("snapshot");p.add_argument("--title",required=True);p.add_argument("--id");p.add_argument("--note",default="");p.add_argument("--file",action="append",default=[]);p.add_argument("--reference",action="append",default=[]);p.add_argument("--source-repo")
    p=command("plan",help="Publish an expected result without an execution edge")
    p.add_argument("--title",required=True);p.add_argument("--id")
    p.add_argument("--from",dest="parents",action="append",required=True)
    p.add_argument("--expect",required=True);p.add_argument("--output",action="append",default=[])
    p.add_argument("--details",default="",help="Proposed method or fuller explanation")
    p.add_argument("--requires",default="",help="Prerequisite for proceeding; descriptive, not enforced")
    p=command("run",aliases=["acquire"])
    p.add_argument("--plan",help="Reuse a proposed state after user approval")
    p.add_argument("--approved",action="store_true",help="Declare that the user approved executing this plan")
    p.add_argument("--expect",default="",help="Brief description of expected output")
    p.add_argument("--from",dest="parents",action="append",default=[])
    p.add_argument("--source-url",action="append",default=[])
    p.add_argument("--title",required=True);p.add_argument("--id");p.add_argument("--label");p.add_argument("--reason",default="")
    p.add_argument("--input",action="append",default=[]);p.add_argument("--output",action="append",default=[]);p.add_argument("--stdout");p.add_argument("--script",action="append",default=[]);p.add_argument("--environment",action="append",default=[]);p.add_argument("--tool-version",action="append",default=[]);p.add_argument("--source-repo")
    p.add_argument("--explanation",default="",help="Brief author-stated method explanation; not observed execution evidence")
    p.add_argument("--script-excerpt",action="append",default=[],metavar="PATH:START:END",help="Select 1–40 lines from a preserved script; repeat for several excerpts")
    p.add_argument("argv",nargs=argparse.REMAINDER)
    p=command("remove-plan", help="Remove an unused standalone plan");p.add_argument("state");p.add_argument("--revision",required=True,type=int)
    p=command("serve");p.add_argument("--port",type=int,default=None,help="Override the saved viewer port; 0 chooses a free port")
    for name in ("flow","history","recover"):command(name)
    p=command("export");p.add_argument("destination")
    p=command("start")
    p.add_argument("--from",dest="parent",help="Unique state title or ID; omit for an empty project")
    p.add_argument("--record-output",action="store_true",help="Opt in to an unredacted output transcript")
    p=command("save")
    p.add_argument("--title",required=True);p.add_argument("--reason",default="")
    p.add_argument("--output",action="append",required=True);p.add_argument("--script",action="append",default=[])
    p.add_argument("--source-repo");p.add_argument("--from",dest="parent")
    for name in ("pause","resume","status","commands"):command(name)
    p=command("_shell-event")
    p.add_argument("event",choices=["begin","end"]);p.add_argument("--cwd")
    p.add_argument("--exit-code",type=int,default=0);p.add_argument("--pipeline",type=int,nargs="*",default=[])
    args=parser.parse_args()
    store=Store(args.project)
    def resolve(value):
        p=Path(value).expanduser()
        return p if p.is_absolute() else store.root/p
    def current_session():
        ident=os.environ.get("SAIGEN_SESSION")
        if not ident or Path(os.environ.get("SAIGEN_PROJECT","")).resolve()!=store.root:
            raise RecordError("Use this command inside the project's saigen start session")
        return ident
    try:
        if args.command=="verify":
            from .verification_cli import dispatch
            result=dispatch(store,args)
        elif args.command=="pipeline":
            from .workflows.export_cli import dispatch
            result=dispatch(store,args)
        elif args.command=="workflow":
            from .workflows.cli import dispatch
            result=dispatch(store,args)
        elif args.command=="setup":
            from .workspace import setup
            result=setup(args.workspace,args.agent,args.analysis_project,args.input,args.viewer,args.permissions,args.ui_development)
        elif args.command=="init":
            from .onboarding import initialize
            return initialize(store,existing_project=args.existing_project,history_files=args.history_file,name=args.name,agents=args.agent,port=args.port,
                              permission=args.permissions,ui_development=args.ui_development,non_interactive=args.non_interactive,start_viewer=args.start_viewer)
        elif args.command=="groups":
            from .analysis_groups import replace, show
            if args.operation=="show":result=show(store)
            else:result=replace(store,json.loads(Path(args.file).read_text(encoding="utf-8")),args.revision,args.actor or "AI agent")
        elif args.command=="explain":
            from .story import append
            result=append(store,json.loads(Path(args.file).read_text()),args.revision,args.actor or "AI agent")
        elif args.command=="story":
            from .story import read
            result=read(store,args.state)
        elif args.command=="reconstruct":
            from .reconstruction import propose, review, show
            if args.agent and args.operation!="sources":raise RecordError("--agent is only for reconstruct sources")
            if args.operation=="sources":
                from .reconstruction_sources import sources
                result=sources(store.root,args.agent)
            elif args.operation=="show":result=show(store,args.id)
            elif args.revision is None:raise RecordError("Supply --revision after reviewing the current project")
            elif args.operation=="propose":
                if not args.file:raise RecordError("Supply --file")
                result=propose(store,json.loads(Path(args.file).read_text()),args.revision,args.actor or "AI agent")
            else:result=review(store,args.id,args.operation,args.revision,args.actor or "Human",state_id=args.state,connection_id=args.connection,evidence_id=args.evidence,reason=args.reason)
        elif args.command=="annotate":
            f=store.flow()
            sid=sessions.resolve_state(f,args.state)
            result=store.edit([{"op":"edit_state","id":sid,"changes":{"note":args.note}}],f["revision"],args.actor or "AI agent")
        elif args.command=="remove-plan":
            result=store.edit([{"op":"delete_state","id":args.state}],args.revision,args.actor or "AI agent")
        elif args.command=="snapshot":
            result=store.snapshot(args.title,[resolve(p) for p in args.file],args.actor or "AI agent",args.note,args.id,[resolve(p) for p in args.reference],code_info(args.source_repo or store.root))
        elif args.command=="plan":
            flow=store.flow()
            parents=[]
            for selector in args.parents:
                matches=[n for n in flow["states"] if n["id"]==selector] or [n for n in flow["states"] if n["title"]==selector]
                if len(matches)!=1: raise RecordError("Planned input is missing or ambiguous")
                parents.append(matches[0]["id"])
            result=store.plan(args.title,parents,args.expect,args.output,args.actor or "AI agent",args.id,
                              details=args.details,requires=args.requires)
        elif args.command in {"run","acquire"}:
            if args.command=="run" and not args.parents: raise RecordError("A run needs --from; use acquire for a root download")
            if args.command=="acquire" and (args.parents or args.plan): raise RecordError("Acquisition has no parent or planned target")
            if args.plan and not args.approved:
                raise RecordError("Execute a proposed state only after user approval; supply --approved")

            argv=args.argv[1:] if args.argv[:1]==["--"] else args.argv
            actor=args.actor or (sessions.session(store.flow(),os.environ["SAIGEN_SESSION"])["actor"] if os.environ.get("SAIGEN_SESSION") and Path(os.environ.get("SAIGEN_PROJECT","")).resolve()==store.root else "AI agent")
            parents=[sessions.resolve_state(store.flow(),p) for p in args.parents]
            result=run(store,parents,args.title,argv,inputs=args.input,outputs=args.output,actor=actor,reason=args.reason,label=args.label,ident=args.id,stdout_name=args.stdout,source_repo=args.source_repo,scripts=args.script,environment_files=args.environment,tool_versions=args.tool_version,planned=args.plan,expected=args.expect,acquisition=args.command=="acquire",source_urls=args.source_url,explanation=args.explanation,script_excerpts=args.script_excerpt)
            print(json.dumps(result,indent=2))
            return 0 if result["status"]=="completed" else 130 if result["status"]=="cancelled" else 1
        elif args.command=="serve":
            from .onboarding import saved_port
            port=args.port if args.port is not None else saved_port(store)
            if not 0<=port<=65535: raise RecordError("Choose a port number from 0 to 65535.")
            serve(store,port);return 0
        elif args.command=="flow":result=store.flow()
        elif args.command=="history":result=store.events()
        elif args.command=="recover":store.recover();result=store.flow()
        elif args.command=="export":result={"export":str(store.export(args.destination))}
        elif args.command=="start":
            from .shell_session import start
            return start(store,args.parent,args.actor or "Human",args.record_output)
        elif args.command=="save":
            result=sessions.save(store,current_session(),args.title,args.output,args.reason,args.script,args.source_repo,args.parent)
        elif args.command in {"pause","resume"}:
            result=sessions.pause(store,current_session(),args.command=="pause")
        elif args.command in {"status","commands"}:
            s=sessions.session(store.flow(),current_session())
            result=s["commands"][s["cursor"]:] if args.command=="commands" else {k:v for k,v in s.items() if k!="commands"}
        elif args.command=="_shell-event":
            ident=current_session()
            if args.event=="begin":sessions.command_start(store,ident,sys.stdin.read(20001),args.cwd)
            else:sessions.command_end(store,ident,args.exit_code,args.pipeline)
            return 0
        print(json.dumps(result,indent=2))
        return 0
    except (RecordError,OSError,ValueError) as exc:
        print(json.dumps({"error":str(exc)}),file=sys.stderr)
        return 2

if __name__=="__main__":raise SystemExit(main())
