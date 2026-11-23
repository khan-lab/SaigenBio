"""Agent-facing commands for the pipeline export agreement."""
import argparse
import os

from ..records import RecordError
from . import export


def register(command):
    parser = command("pipeline", help="Review and export pipelines from recorded results")
    subcommands = parser.add_subparsers(dest="pipeline_command", required=True)
    for name in ("show", "propose", "approve", "generate"):
        sub = subcommands.add_parser(name)
        sub.add_argument("--project", default=argparse.SUPPRESS)
        sub.add_argument("--actor", default=argparse.SUPPRESS)
        if name != "show":
            sub.add_argument("--revision", type=int, required=True)
        if name != "propose":
            sub.add_argument("id")
        else:
            selection = sub.add_mutually_exclusive_group(required=True)
            selection.add_argument("--selection")
            selection.add_argument("--target", action="append")
            sub.add_argument("--start-from", action="append", default=[])
            sub.add_argument("--provide-script", action="append", default=[], metavar="STATE=PATH")
            sub.add_argument("--engine", choices=("nextflow", "snakemake"), required=True)
        if name == "approve":
            sub.add_argument("--digest", required=True)
            sub.add_argument("--researcher", required=True)
            sub.add_argument("--agent-session")
            sub.add_argument("--draft", action="store_true")


def dispatch(store, args):
    actor = args.actor or "AI agent"
    if args.pipeline_command == "show":
        return export.show(store, args.id)
    if args.pipeline_command == "propose":
        replacements = {}
        for entry in args.provide_script:
            state, separator, path = entry.partition("=")
            if not separator or not state or not path or state in replacements:
                raise RecordError("Provide one replacement per step as STATE=PATH")
            replacements[state] = path
        return export.propose(store, args.selection, args.target, args.start_from,
                              args.engine, args.revision, actor, replacements)
    if args.pipeline_command == "approve":
        session = args.agent_session or os.environ.get("CODEX_THREAD_ID")
        if not session:
            raise RecordError("Supply your active agent session reference with --agent-session")
        return export.approve(store, args.id, args.digest, session, args.researcher, args.draft, args.revision, actor)
    return export.generate(store, args.id, args.revision, actor)
