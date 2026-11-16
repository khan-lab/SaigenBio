"""Explicit registry; installing SaigenBio never installs a workflow engine."""
from ...store import RecordError


def engines():
    return []


def adapter(name):
    raise RecordError(f"Workflow engine {name!r} is not supported yet. No engine was installed or executed.")
