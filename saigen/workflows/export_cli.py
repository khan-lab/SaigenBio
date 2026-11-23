"""Agent-facing commands for the pipeline export agreement."""
import argparse
import os
import time

from ..records import RecordError
from . import export


def register(command):
    parser = command("pipeline", help="Review and export pipelines from recorded results")
    subcommands = parser.add_subparsers(dest="pipeline_command", required=True)
    for name in ("request", "requests", "wait", "cancel-request", "show", "propose", "approve", "generate"):
        sub = subcommands.add_parser(name)
        sub.add_argument("--project", default=argparse.SUPPRESS)
        sub.add_argument("--actor", default=argparse.SUPPRESS)
        if name in {"request", "cancel-request", "propose", "approve", "generate"}:
            sub.add_argument("--revision", type=int, required=True)
        if name in {"show", "wait", "cancel-request", "approve", "generate"}:
            sub.add_argument("id")
        if name == "propose":
            selection = sub.add_mutually_exclusive_group(required=True)
            selection.add_argument("--selection")
            selection.add_argument("--target", action="append")
            sub.add_argument("--start-from", action="append", default=[])
            sub.add_argument("--provide-script", action="append", default=[], metavar="STATE=PATH")
            sub.add_argument("--engine", choices=("nextflow", "snakemake"), required=True)
        if name in {"request", "requests", "wait", "cancel-request", "propose", "approve"}:
            sub.add_argument("--agent-session")
        if name == "wait":
            sub.add_argument("--timeout", type=int, choices=range(1, 31), metavar="SECONDS", default=25)
        if name == "approve":
            sub.add_argument("--digest", required=True)
            sub.add_argument("--researcher", required=True)
            sub.add_argument("--draft", action="store_true")


def dispatch(store, args):
    actor = args.actor or "AI agent"
    if args.pipeline_command == "show":
        return export.show(store, args.id)
    command = args.pipeline_command
    session = getattr(args, "agent_session", None) or os.environ.get("CODEX_THREAD_ID")
    if command in {"request", "requests", "wait", "cancel-request", "approve"} and not session:
        raise RecordError("Supply your active agent session reference with --agent-session")
    if command == "request":
        return export.request_selection(store, session, args.revision, actor)
    if command == "requests":
        return export.requests(store, session)
    if command == "cancel-request":
        return export.cancel_request(store, args.id, session, args.revision, actor)
    if command == "wait":
        deadline = time.monotonic() + args.timeout
        while True:
            selection = export.show(store, args.id)
            if selection.get("agentSession") != session:
                raise RecordError("Choose a Canvas request from this agent session")
            remaining = deadline - time.monotonic()
            if selection["status"] != "pending" or remaining <= 0:
                return selection
            time.sleep(min(0.5, remaining))
    if command == "propose":
        replacements = {}
        for entry in args.provide_script:
            state, separator, path = entry.partition("=")
            if not separator or not state or not path or state in replacements:
                raise RecordError("Provide one replacement per step as STATE=PATH")
            replacements[state] = path
        return export.propose(store, args.selection, args.target, args.start_from,
                              args.engine, args.revision, actor, replacements, session=session)
    if args.pipeline_command == "approve":
        return export.approve(store, args.id, args.digest, session, args.researcher, args.draft, args.revision, actor)
    return export.generate(store, args.id, args.revision, actor)
