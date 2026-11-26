"""Explicit registry; engine installation remains a separate user choice."""
from dataclasses import asdict
from ...records import RecordError
from .nextflow import NextflowAdapter
from .snakemake import SnakemakeAdapter


_ADAPTERS = {'nextflow': NextflowAdapter, 'snakemake': SnakemakeAdapter}


def engines():
    return [asdict(cls().discover()) for cls in _ADAPTERS.values()]


def adapter(name):
    if name not in _ADAPTERS:
        raise RecordError(f'Workflow engine {name!r} is not supported')
    return _ADAPTERS[name]()
