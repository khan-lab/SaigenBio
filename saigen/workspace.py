"""Prepare portable recording instructions without replacing user files."""
import json
from pathlib import Path
import sysconfig
import sys
from .store import RecordError

ADAPTERS = {
    "codex": (".agents/skills", "AGENTS.md"),
    "claude": (".claude/skills", "CLAUDE.md"),
    "opencode": (".opencode/skills", "AGENTS.md"),
    "antigravity": (".agents/skills", "GEMINI.md"),
}

def setup(workspace, agent, project, inputs, viewer):
    root = Path(workspace).expanduser().resolve()
    source = Path(__file__).resolve().parent.parent / "skills/saigen-record/SKILL.md"
    if not source.is_file():
        source = Path(sysconfig.get_path("data")) / "share/saigenbio/skills/saigen-record/SKILL.md"
    if not source.is_file():
        raise RecordError("Bundled recording skill is missing")
    folder, instructions = ADAPTERS[agent]
    skill = folder + "/saigen-record/SKILL.md"
    context = {"project": project, "inputs": list(inputs), "viewer": viewer,
               "pathsRelativeTo": "workspace", "agent": agent,
               "cli": str(Path(sys.executable).parent / "saigen"), "python": sys.executable}
    files = {
        "saigen-workspace.json": json.dumps(context, indent=2) + "\n",
        skill: source.read_text(),
        instructions: "# SaigenBio analysis workspace\n\n"
            "For analysis requests, read saigen-workspace.json for the active project, "
            "available inputs, and viewer. Paths are relative to this workspace. "
            "Read and follow " + skill + " even when the user does not name SaigenBio. "
            "Use the exact cli path in saigen-workspace.json rather than another saigen found on PATH. Inspect existing records before importing or executing. "
            "Do not launch a duplicate viewer. Stop at the requested scientific decision checkpoint.\n",
    }
    # Preflight every destination before writing any content.
    for name, content in files.items():
        dest = root / name
        if dest.exists() and (not dest.is_file() or dest.read_text() != content):
            raise RecordError("Existing file differs: " + str(dest) + ". Merge instructions manually or choose a fresh workspace.")
    root.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        dest = root / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content)
    return {"workspace":str(root), "agent":agent, "files":list(files),
            "verification":"Setup generated; fresh-agent behavior requires testing."}
