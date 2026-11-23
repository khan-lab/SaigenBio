"""Record pipeline selection, proposal, agreement and generation."""
import hashlib
import json
import os
from pathlib import Path
import tempfile

from ..records import RecordError, now, text, uid
from .export_plan import build, state_ids
from .export_render import RUNNER, nextflow, snakemake
from .models import canonical


def _get(flow, kind, ident):
    record = flow.get("pipelineExports", {}).get(kind, {}).get(ident)
    if record is None:
        raise RecordError(f"Unknown pipeline {kind.rstrip('s')}: {ident}")
    return record


def _save(flow, kind, record):
    flow.setdefault("pipelineExports", {}).setdefault(kind, {})[record["id"]] = record


def request_selection(store, session, revision, actor):
    text(session, "active agent session", 300, True)
    ident = uid("selection")

    def change(flow):
        selections = flow.get("pipelineExports", {}).get("selections", {})
        if any(r.get("status") == "pending" and r.get("agentSession") == session for r in selections.values()):
            raise RecordError("This session already has a pending Canvas request. Resume or cancel it first.")
        record = {"id": ident, "status": "pending", "agent": actor, "agentSession": session, "requestedAt": now()}
        _save(flow, "selections", record)
        return record, None

    return _get(store.update("pipeline.selection_requested", actor, change, revision), "selections", ident)


def select(store, ident, selected, revision, actor):
    def change(flow):
        record = _get(flow, "selections", ident)
        if record.get("status") != "pending":
            raise RecordError("This Canvas request is no longer pending")
        ids = state_ids(selected, {node["id"]: node for node in flow["states"]}, "target", required=True)
        record.update(status="ready", targets=ids, sourceRevision=revision)
        return record, None

    return _get(store.update("pipeline.selected", actor, change, revision), "selections", ident)


def requests(store, session):
    flow = store.flow()
    selections = flow.get("pipelineExports", {}).get("selections", {})
    return {"revision": flow["revision"], "requests": [record for record in selections.values()
            if record.get("agentSession") == session and record.get("status") != "cancelled"]}


def cancel_request(store, ident, session, revision, actor):
    def change(flow):
        record = _get(flow, "selections", ident)
        if record.get("agentSession") != session or record.get("status") != "pending":
            raise RecordError("Choose a pending Canvas request from this agent session")
        record["status"] = "cancelled"
        return record, None

    return _get(store.update("pipeline.selection_cancelled", actor, change, revision), "selections", ident)


def propose(store, selection, targets, boundary, engine, revision, actor, replacements=None, *, session=None):
    ident = uid("pipeline")

    def change(flow):
        target_ids = targets
        request = _get(flow, "selections", selection) if selection else None
        if request:
            if request.get("agentSession") and (request.get("status") != "ready" or request["agentSession"] != session):
                raise RecordError("Use a confirmed Canvas selection from this agent session")
            target_ids = request["targets"]
        supplied = {}
        for sid, path in (replacements or {}).items():
            item = store.capture(store.root / Path(path).expanduser(), role="code")
            flow["artifacts"][item["id"]] = item
            supplied[sid] = item
        plan = build(flow, store.root, target_ids, boundary, engine, supplied)
        record = {"id": ident, "selectionId": selection, "sourceRevision": revision, "plan": plan}
        if request and request.get("agentSession"):
            record["agentSession"] = session
            record["selectionRevision"] = request["sourceRevision"]
        record["digest"] = hashlib.sha256(canonical(record).encode()).hexdigest()
        _save(flow, "proposals", record)
        return record, None

    flow = store.update("pipeline.proposed", actor, change, revision)
    return {**_get(flow, "proposals", ident), "revision": flow["revision"]}


def show(store, ident):
    flow = store.flow()
    if ident.startswith("selection_"):
        record = _get(flow, "selections", ident)
        nodes = {node["id"]: node["title"] for node in flow["states"]}
        return {**record, "revision": flow["revision"],
                "targetDetails": [{"stateId": sid, "title": nodes.get(sid)} for sid in record.get("targets", [])]}
    return {**_get(flow, "proposals", ident), "revision": flow["revision"]}


def approve(store, ident, digest, agent_session, researcher, draft, revision, actor):
    text(agent_session, "active agent session", 300, True)
    text(researcher, "researcher", 120, True)

    def change(flow):
        record = _get(flow, "proposals", ident)
        if record.get("agentSession") and record["agentSession"] != agent_session:
            raise RecordError("Record agreement in the agent session that requested these targets")
        if record["digest"] != digest:
            raise RecordError("Review the proposal and use its exact digest")
        if record.get("approval"):
            raise RecordError("This pipeline proposal already has an agreement")
        if bool(record["plan"]["gaps"]) != draft:
            raise RecordError("Explicitly agree to an incomplete draft when the proposal has gaps")
        agreement = {"digest": digest, "agent": actor, "agentSession": agent_session,
                     "researcher": researcher, "at": now(), "draft": draft}
        record["approval"] = agreement
        return {"proposal": ident, **agreement}, None

    flow = store.update("pipeline.approved", actor, change, revision)
    return {**_get(flow, "proposals", ident), "revision": flow["revision"]}


def _files(store, record):
    plan = record["plan"]
    draft = record["approval"]["draft"]
    engine = plan["engine"]
    format_name = "main.nf" if engine == "nextflow" else "Snakefile"
    files = {"manifest.json": json.dumps(record, indent=2) + "\n",
             "bundle/configuration.json": json.dumps({step["key"]: step for step in plan["steps"]}, indent=2) + "\n"}
    readme = ["# Generated SaigenBio pipeline", "", f"Format: {engine}", "", "## Inputs", ""]
    readme.extend(f"- Put {entry['name']} at `{entry['path']}` (original SHA-256 `{entry['sha256']}`)."
                  for entry in plan["inputs"])
    readme.extend(["", "## Targets", ""])
    for target in plan["targets"]:
        readme.extend(f"- {target['title']}: `{path}`" for path in target["paths"])
    readme.extend(["", "## Configuration", "",
                   "Review the recorded command arguments in `bundle/configuration.json`. "
                   "The workflow requires Python 3 and the tools and libraries used by the recorded steps. "
                   "See the manifest for captured version declarations."])
    if draft:
        readme += ["", "## Incomplete draft", "", "Resolve these gaps and review a revised proposal before running."]
        readme.extend(f"- {gap['stateId']}: {gap['message']}" for gap in plan["gaps"])
        files[format_name] = "workflow { error 'Incomplete SaigenBio pipeline draft. See README.md.' }\n" if engine == "nextflow" else '# Incomplete draft. See README.md.\nraise ValueError("Incomplete SaigenBio pipeline draft. See README.md.")\n'
    else:
        files[format_name] = nextflow(plan) if engine == "nextflow" else snakemake(plan)
        files["bundle/run_step.py"] = RUNNER
        cmd = "nextflow run main.nf" if engine == "nextflow" else "snakemake --cores 1 --scheduler greedy"
        readme.extend(["", "## Run", "", "From this directory:", "", f"`{cmd}`",
                       "", "Generated files have not been executed by SaigenBio."])
    for step in plan["steps"]:
        for script in step["scripts"]:
            item = store.artifact(script["artifactId"])
            files[f"bundle/{step['key']}/{script['name']}"] = store.artifact_path(item).read_bytes()
    files["README.md"] = "\n".join(readme) + "\n"
    return {name: body.encode() if isinstance(body, str) else body for name, body in files.items()}


def generate(store, ident, revision, actor):
    parent = store.home / "pipelines"

    def change(flow):
        record = _get(flow, "proposals", ident)
        if not record.get("approval") or record["approval"]["digest"] != record["digest"]:
            raise RecordError("Record the researcher's agreement in the active SaigenBio agent session first")
        if record.get("generated"):
            raise RecordError("This pipeline has already been generated. Use pipeline show for its files.")
        files = _files(store, record)
        parent.mkdir(exist_ok=True)
        destination = parent / ident
        if destination.exists():
            # A prior process may have published the files before committing the event.
            if (not destination.is_dir() or destination.is_symlink()
                    or {p.relative_to(destination).as_posix() for p in destination.rglob("*") if p.is_file()} != files.keys()
                    or any((destination / name).read_bytes() != body for name, body in files.items())):
                raise RecordError("The export destination already contains different files")
        else:
            with tempfile.TemporaryDirectory(dir=parent) as temporary:
                staged = Path(temporary) / "export"
                for name, body in files.items():
                    path = staged / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(body)
                os.rename(staged, destination)
        event = {"proposal": ident, "directory": str(destination), "files": sorted(files),
                 "draft": record["approval"]["draft"], "at": now()}
        record["generated"] = event
        return event, None

    return _get(store.update("pipeline.generated", actor, change, revision), "proposals", ident)["generated"]
