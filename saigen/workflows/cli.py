"""Thin CLI over the workflow service; approval never starts execution."""
import json
from pathlib import Path
from ..store import RecordError
from .service import WorkflowService
from .adapters.registry import engines


def register(command):
    parser = command("workflow", help="Publish and review workflow proposals (execution not yet supported)")
    commands = parser.add_subparsers(dest="workflow_command", required=True)
    commands.add_parser("engines")
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
        return {"engines": engines(), "executionSupported": False}
    if args.workflow_command == "show":
        return service.show(args.proposal)
    if args.workflow_command == "approve":
        return service.approve(args.proposal, args.digest, revision=args.revision, actor=args.actor or "AI agent")
    try:
        spec = json.loads(Path(args.spec).expanduser().read_text())
    except (ValueError, UnicodeError) as exc:
        raise RecordError("Invalid workflow proposal JSON") from exc
    return service.propose(spec, revision=args.revision, actor=args.actor or "AI agent")
