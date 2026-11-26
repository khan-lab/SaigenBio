"""Adapter boundary: structured inspection and evidence, never database writes."""
from dataclasses import dataclass, field
from pathlib import Path
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
    environment_files: tuple[str, ...] = ('params.json', 'saigen.config')
    env: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class EvidenceBatch:
    events: tuple[dict, ...]
    cursor: str | None


class WorkflowAdapter(Protocol):
    display_name: str
    mapping_key: str
    evidence_source: str
    work_directory: str
    task_script: str | None

    def discover(self) -> EngineInfo: ...
    def inspect(self, source: str, configuration: dict) -> dict: ...
    def prepare(self, proposal: dict) -> LaunchSpec: ...
    def stage(self, proposal: dict, folder: Path, parameters: dict, launch: LaunchSpec) -> LaunchSpec: ...
    def run_identity(self, folder: Path) -> str | None: ...
    def collect(self, run_reference: str, cursor: str | None) -> EvidenceBatch: ...
