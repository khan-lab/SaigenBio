"""Thin CLI over the workflow service; approval never starts execution."""
import json
from pathlib import Path
from ..records import RecordError
from .service import WorkflowService
from .adapters.registry import engines


def register(command):
    parser = command("workflow", help="Publish and review workflow proposals (local Nextflow execution)")
    commands = parser.add_subparsers(dest="workflow_command", required=True)
    commands.add_parser("engines")
    commands.add_parser("recover")
    inspect = commands.add_parser("inspect")
    inspect.add_argument("--engine", required=True)
    inspect.add_argument("--source", required=True)
    execute = commands.add_parser("execute")
    execute.add_argument("proposal")
    execute.add_argument("--revision", required=True, type=int)
    cancel = commands.add_parser("cancel", help="Retire an unexecuted proposal and remove its planned cards")
    cancel.add_argument("proposal")
    cancel.add_argument("--revision", required=True, type=int)
    cancel.add_argument("--reason", required=True)
    status = commands.add_parser("status")
    status.add_argument("run")
    propose = commands.add_parser("propose")
    propose.add_argument("--spec", required=True)
    propose.add_argument("--revision", required=True, type=int)
    show = commands.add_parser("show")
    show.add_argument("proposal")
    approve = commands.add_parser("approve", help="Declare the user's agreement to this specific proposal")
    approve.add_argument("proposal")
    approve.add_argument("--digest", required=True)
    approve.add_argument("--revision", required=True, type=int)


def dispatch(store, args):
    service = WorkflowService(store)
    if args.workflow_command == "engines":
        return {"engines": engines(), "executionSupported": True}
    if args.workflow_command == "recover":
        from .execution import recover
        return recover(store)
    if args.workflow_command == "inspect":
        from .adapters.registry import adapter
        return adapter(args.engine).inspect(args.source, {})
    if args.workflow_command == "execute":
        from .execution import execute
        return execute(service, args.proposal, args.revision)
    if args.workflow_command == "status":
        from .repository import run
        return run(store.flow(), args.run)
    if args.workflow_command == "cancel":
        return service.cancel(args.proposal, revision=args.revision, reason=args.reason, actor=args.actor or "AI agent")
    if args.workflow_command == "show":
        return service.show(args.proposal)
    if args.workflow_command == "approve":
        return service.approve(args.proposal, args.digest, revision=args.revision, actor=args.actor or "AI agent")
    try:
        spec = json.loads(Path(args.spec).expanduser().read_text())
    except (ValueError, UnicodeError) as exc:
        raise RecordError("Invalid workflow proposal JSON") from exc
    return service.propose(spec, revision=args.revision, actor=args.actor or "AI agent")
