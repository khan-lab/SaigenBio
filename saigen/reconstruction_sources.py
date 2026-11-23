"""List reconstruction source candidates without importing transcripts."""
from datetime import datetime
import json
import os
from pathlib import Path

from .records import RecordError
from .workspace import git_worktree_root

MAX_CODEX_HEADERS = 1000
MAX_HEADER_BYTES = 64 * 1024


def _codex_metadata(path):
    try:
        with path.open("rb") as handle:
            line = handle.readline(MAX_HEADER_BYTES + 1)
        if len(line) > MAX_HEADER_BYTES:
            return None
        record = json.loads(line)
        if isinstance(record, dict) and record.get("type") == "session_meta":
            payload = record.get("payload")
            if isinstance(payload, dict):
                return payload
    except (OSError, ValueError):
        pass
    return None


def _codex_sources(directories):
    home = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex").expanduser().resolve()
    paths = []
    readable = False
    for folder, pattern in (
        ("sessions", "[0-9][0-9][0-9][0-9]/[0-9][0-9]/[0-9][0-9]/rollout-*.jsonl"),
        ("archived_sessions", "rollout-*.jsonl"),
    ):
        root = home / folder
        if root.is_symlink():
            continue
        try:
            with os.scandir(root):
                paths.extend(root.glob(pattern))
                readable = True
        except OSError:
            continue
    if not readable:
        return "unavailable", [], False

    current_thread = os.environ.get("CODEX_THREAD_ID")
    candidates = []
    for path in sorted(paths, key=lambda p: (p.name, str(p)), reverse=True)[:MAX_CODEX_HEADERS]:
        try:
            if path.resolve() != path or not path.is_file():
                continue
        except (OSError, RuntimeError):
            continue
        meta = _codex_metadata(path)
        if not meta:
            continue
        session_id = meta.get("id")
        if current_thread and session_id == current_thread:
            continue
        cwd, timestamp = meta.get("cwd"), meta.get("timestamp")
        if not isinstance(cwd, str) or not isinstance(timestamp, str):
            continue
        try:
            project = Path(cwd)
            if not project.is_absolute() or project.resolve() not in directories:
                continue
            date = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except (ValueError, OSError, RuntimeError):
            continue
        candidates.append({
            "path": str(path), "origin": "discovered",
            "directory": str(project), "timestamp": date.isoformat(),
        })
    return ("discovered" if candidates else "no-matches"), candidates, len(paths) > MAX_CODEX_HEADERS


_DISCOVERY = {"codex": _codex_sources}


def sources(workspace, agent=None):
    """Return configured paths or suggestions for a single agent and project."""
    config_file = workspace / "saigen-workspace.json"
    try:
        config = json.loads(config_file.read_text(encoding="utf-8"))
    except FileNotFoundError:
        config = {}
    if not isinstance(config, dict):
        raise RecordError("Invalid SaigenBio workspace configuration")

    context = config.get("reconstruction", {})
    if not isinstance(context, dict):
        raise RecordError("Invalid reconstruction context in saigen-workspace.json")
    directory = context.get("directory", config.get("project", "."))
    configured = context.get("sources", [])
    if (not isinstance(directory, str) or not isinstance(configured, list)
            or any(not isinstance(path, str) for path in configured)):
        raise RecordError("Invalid reconstruction source paths in saigen-workspace.json")
    analysis = (workspace / Path(directory).expanduser()).resolve()
    if agent is None:
        agents = config.get("agents")
        if isinstance(agents, list) and len(agents) == 1:
            agent = agents[0]
        elif not agents:
            agent = config.get("agent")
    discover = _DISCOVERY.get(agent) if isinstance(agent, str) else None
    if configured:
        status = "configured"
        candidates = []
        for source in configured:
            path = workspace / Path(source).expanduser()
            candidates.append({"path": str(path), "origin": "configured", "available": path.is_file()})
        limited = False
    elif discover:
        directories = {workspace, analysis}
        directories.update(root for path in (workspace, analysis) if (root := git_worktree_root(path)))
        status, candidates, limited = discover(directories)
    else:
        status, candidates, limited = "unsupported", [], False
    return {
        "directory": str(analysis), "agent": agent, "status": status,
        "candidates": candidates, "scanLimited": limited,
    }
