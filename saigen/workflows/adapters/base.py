"""Adapter boundary: structured inspection and evidence, never database writes."""
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class EngineInfo:
    name: str
    version: str | None
    available: bool
    capabilities: dict


@dataclass(frozen=True)
class LaunchSpec:
    argv: tuple[str, ...]
    cwd: str
    evidence_locations: tuple[str, ...]


@dataclass(frozen=True)
class EvidenceBatch:
    events: tuple[dict, ...]
    cursor: str | None


class WorkflowAdapter(Protocol):
    def discover(self) -> EngineInfo: ...
    def inspect(self, source: str, configuration: dict) -> dict: ...
    def prepare(self, proposal: dict) -> LaunchSpec: ...
    def collect(self, run_reference: str, cursor: str | None) -> EvidenceBatch: ...
