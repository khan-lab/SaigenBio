"""Workflow records use the recorder's revision-checked SQLite transaction."""
from ..records import RecordError


def collection(flow):
    return flow.setdefault("workflows", {"schemaVersion": 1, "proposals": {}, "runs": {}})


def proposal(flow, ident):
    try:
        return collection(flow)["proposals"][ident]
    except KeyError as exc:
        raise RecordError("Unknown workflow proposal") from exc


def run(flow, ident):
    try:
        return collection(flow)["runs"][ident]
    except KeyError as exc:
        raise RecordError("Unknown workflow run") from exc


def require_active(proposal):
    if proposal.get("retirement"):
        raise RecordError("This workflow proposal was cancelled; publish a new proposal to proceed")
