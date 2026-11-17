"""Prepare portable recording instructions without replacing user files."""
import json
from pathlib import Path
import sysconfig
import sys
from .records import RecordError

ADAPTERS = {
    "codex": (".agents/skills", "AGENTS.md"),
    "claude": (".claude/skills", "CLAUDE.md"),
    "opencode": (".opencode/skills", "AGENTS.md"),
    "antigravity": (".agents/skills", "GEMINI.md"),
}

PERMISSIONS = {
    "ask": "Ask before starting proposed downloads or analysis runs. Requested workspace edits may proceed.",
    "flexible": "Proceed with edits, public-data downloads, and analysis runs needed for the user's requested work in this workspace without asking again for each step. The user also authorizes routine local fixes and improvements to SaigenBio's own UI implementation without separate approval for each edit. Locate its source checkout before editing; do not assume the analysis workspace or an installed package is the UI source.",
}

ANALYSIS_PERMISSIONS = {
    "ask": PERMISSIONS["ask"],
    "flexible": "Proceed with edits, public-data downloads, and analysis runs needed for the user's requested work in this workspace without asking again for each step.",
}

UI_DEVELOPMENT = {
    "ask": "Ask before changing SaigenBio's application source code.",
    "allow": "The user authorizes routine local fixes and improvements to SaigenBio's own UI implementation without separate approval for each edit. Locate its source checkout before editing; do not assume the analysis workspace or an installed package is the UI source.",
}


def permission_instructions(permission, ui_development=None):
    # Missing scope retains the exact legacy policy for existing workspaces.
    if ui_development is None:
        return PERMISSIONS[permission] if permission else ""
    analysis = ANALYSIS_PERMISSIONS[permission] if permission else ""
    return (analysis + " " + UI_DEVELOPMENT[ui_development]).strip()


def instruction_files(agents, skill_text, permission=None, ui_development=None):
    files = {}
    groups = {}
    for agent in agents:
        folder, instructions = ADAPTERS[agent]
        skill = folder + "/saigen-record/SKILL.md"
        files[skill] = skill_text
        groups.setdefault(instructions, []).append(skill)
    for instructions, skills in groups.items():
        files[instructions] = "# SaigenBio analysis workspace\n\n" \
            "For analysis requests, read saigen-workspace.json for the active project, " \
            "available inputs, viewer, and any reconstruction context. If reconstruction is configured, inspect `saigen reconstruct show` and follow the existing-analysis section of the recording skill. Paths are relative to this workspace. " \
            "Read and follow " + " and ".join(skills) + " even when the user does not name SaigenBio. " \
            "Use the exact cli path in saigen-workspace.json rather than another saigen found on PATH. Inspect existing records before importing or executing. " \
            "Do not launch a duplicate viewer. Stop at the requested scientific decision checkpoint.\n"
        if permission or ui_development:
            files[instructions] += "\n" + permission_instructions(permission, ui_development) + " " \
                "Planning-only requests and explicit review checkpoints still require waiting. " \
                "Ask before destructive changes, uploads, spending money, or work outside the requested scope. " \
                "This workflow preference does not grant filesystem or network access or override host permissions.\n"
    return files

BLOCK_START = "<!-- saigenbio:instructions:start -->"
BLOCK_END = "<!-- saigenbio:instructions:end -->"


def merge_instructions(existing, content, previous=None):
    """Preserve user text; replace only an unchanged, explicitly managed block."""
    block = BLOCK_START + "\n" + content + BLOCK_END
    if BLOCK_START not in existing and BLOCK_END not in existing:
        return existing + ("\n\n" if existing else "") + block + "\n"
    if existing.count(BLOCK_START) != 1 or existing.count(BLOCK_END) != 1:
        raise RecordError("Invalid SaigenBio instruction markers; merge instructions manually")
    start = existing.index(BLOCK_START)
    end = existing.index(BLOCK_END)
    if end < start or existing[start + len(BLOCK_START):end] not in ("\n" + content, "\n" + (previous or content)):
        raise RecordError("SaigenBio instruction block was edited; merge instructions manually")
    return existing[:start] + block + existing[end + len(BLOCK_END):]


def prepare(workspace, agent, project, inputs, viewer=None, permission=None, ui_development=None, *, preserve_instructions=False):
    """Build and preflight all files before initialization or setup writes anything."""
    root = Path(workspace).expanduser().resolve()
    source = Path(__file__).resolve().parent.parent / "skills/saigen-record/SKILL.md"
    if not source.is_file():
        source = Path(sysconfig.get_path("data")) / "share/saigenbio/skills/saigen-record/SKILL.md"
    if not source.is_file():
        raise RecordError("Bundled recording skill is missing")
    agents = list(dict.fromkeys([agent] if isinstance(agent, str) else agent))
    if any(a not in ADAPTERS for a in agents):
        raise RecordError("Unknown AI agent")
    if permission is not None and permission not in PERMISSIONS:
        raise RecordError("Unknown workflow permission mode")
    if ui_development is not None and ui_development not in UI_DEVELOPMENT:
        raise RecordError("Unknown UI development permission")
    previous = {}
    config = root / "saigen-workspace.json"
    if config.is_file():
        try:
            previous = json.loads(config.read_text())
        except (ValueError, UnicodeError) as exc:
            raise RecordError("Invalid workspace configuration: " + str(config)) from exc
        if not isinstance(previous, dict):
            raise RecordError("Invalid workspace configuration: " + str(config))
        for key, value in (("project", project), ("inputs", list(inputs))):
            if previous.get(key) != value:
                raise RecordError("Existing file differs: " + str(config) + ". Merge instructions manually or choose a fresh workspace.")
        if viewer is not None and previous.get("viewer") != viewer:
            raise RecordError("Existing viewer differs: " + str(config) + ". Update it deliberately before setup.")
        if permission is not None and previous.get("permissionMode", "ask") != permission:
            raise RecordError("Existing workflow permission differs. Update workspace instructions deliberately.")
        if ui_development is not None and previous.get("uiDevelopment", "allow" if previous.get("permissionMode") == "flexible" else "ask") != ui_development:
            raise RecordError("Existing UI development permission differs. Update workspace instructions deliberately.")
        ui_development = previous.get("uiDevelopment", ui_development)
        if ui_development is not None and (not isinstance(ui_development, str) or ui_development not in UI_DEVELOPMENT):
            raise RecordError("Unknown UI development permission in workspace configuration")
        old_agents = previous.get("agents") or ([previous["agent"]] if previous.get("agent") else [])
        if not isinstance(old_agents, list) or any(not isinstance(a,str) or a not in ADAPTERS for a in old_agents):
            raise RecordError("Invalid agents in workspace configuration")
        agents = list(dict.fromkeys(old_agents + agents))
        permission = previous.get("permissionMode", permission)
        if permission is not None and (not isinstance(permission,str) or permission not in PERMISSIONS):
            raise RecordError("Unknown workflow permission mode in workspace configuration")
    else:
        old_agents = []
        ui_development = ui_development or "ask"
    context = {"project": project, "inputs": list(inputs), "viewer": viewer,
               "pathsRelativeTo": "workspace", "agent": agents[0] if agents else None,
               "cli": str(Path(sys.executable).parent / "saigen"), "python": sys.executable}
    context.update(previous)
    context.update(agents=agents, agent=agents[0] if agents else None)
    context["viewer"] = viewer or previous.get("viewer") or "http://127.0.0.1:8767/"
    if permission is not None:
        context["permissionMode"] = permission
    if ui_development is not None:
        context["uiDevelopment"] = ui_development
    skill_text = source.read_text()
    files = instruction_files(agents, skill_text, permission, ui_development)
    reference=source.parent/"references/reconstruction.md"
    if reference.is_file():
        for selected_agent in agents:
            files[ADAPTERS[selected_agent][0]+"/saigen-record/references/reconstruction.md"]=reference.read_text()
    files["saigen-workspace.json"] = json.dumps(context, indent=2) + "\n"
    old_files = instruction_files(old_agents, skill_text, previous.get("permissionMode"), previous.get("uiDevelopment"))
    instruction_names = {ADAPTERS[a][1] for a in agents}
    managed = dict(previous.get("managedInstructions", {}))
    # Preflight every destination before writing any content.
    for name, content in files.items():
        dest = root / name
        for path in (dest, *dest.parents):
            if path == root.parent:
                break
            if path.is_symlink():
                raise RecordError("Setup will not replace or write through a symlink: " + str(path))
            if path != dest and path.exists() and not path.is_dir():
                raise RecordError("Expected a directory: " + str(path))
        if name in instruction_names and (dest.is_file() or not dest.exists()):
            existing = dest.read_bytes().decode("utf-8") if dest.is_file() else ""
            if name in managed or (preserve_instructions and existing != content and existing != old_files.get(name)):
                files[name] = merge_instructions(existing, content, managed.get(name))
                managed[name] = content
                continue
        if dest.exists() and (not dest.is_file() or dest.read_text() != content):
            if name == "saigen-workspace.json" and previous:
                continue
            if dest.is_file() and dest.read_text() == old_files.get(name):
                continue
            raise RecordError("Existing file differs: " + str(dest) + ". Merge instructions manually or choose a fresh workspace.")
    if managed:
        context["managedInstructions"] = managed
        files["saigen-workspace.json"] = json.dumps(context, indent=2) + "\n"
    return root, files, context

def write_files(root, files):
    root.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        dest = root / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content)

def setup(workspace, agent, project, inputs, viewer=None, permission=None, ui_development=None):
    root, files, context = prepare(workspace, agent, project, inputs, viewer, permission, ui_development)
    write_files(root, files)
    return {"workspace":str(root), "agent":context["agent"], "agents":context["agents"], "files":list(files),
            "verification":"Setup generated; fresh-agent behavior requires testing."}
