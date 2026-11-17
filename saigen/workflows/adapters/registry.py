"""Explicit registry; engine installation remains a separate user choice."""
from dataclasses import asdict
from ...records import RecordError
from .nextflow import NextflowAdapter


def engines():
    return [asdict(NextflowAdapter().discover())]


def adapter(name):
    if name == 'nextflow':
        return NextflowAdapter()
    raise RecordError(f'Workflow engine {name!r} is not supported')
