"""Build a portable, reviewable replay plan from recorded file dependencies."""
from pathlib import Path, PurePosixPath
import re

from ..records import RecordError


def state_ids(value, states, label, *, required=False):
    if (not isinstance(value, list) or (required and not value)
            or any(not isinstance(sid, str) or sid not in states for sid in value)
            or len(set(value)) != len(value)):
        raise RecordError(f"Choose valid, distinct {label} states")
    return value


def portable_name(name):
    return (isinstance(name, str) and re.fullmatch(r"[\w. -]+(?:/[\w. -]+)*", name, re.ASCII)
            and all(part not in {".", ".."} for part in name.split("/")))


SCRIPT_SUFFIXES = {".py", ".r", ".sh", ".pl", ".jl", ".ipynb"}


def build(flow, root, selected, boundary, engine, supplied):
    if engine not in ("nextflow", "snakemake"):
        raise RecordError("Choose Nextflow or Snakemake")
    states = {node["id"]: node for node in flow["states"]}
    state_ids(selected, states, "target", required=True)
    state_ids(boundary, states, "starting")
    artifacts = flow["artifacts"]
    incoming = {}
    for action in flow["actions"]:
        incoming.setdefault(action["to"], []).append(action)

    def producer(sid):
        actions = incoming.get(sid, [])
        if sid in boundary or states[sid]["origin"] == "imported":
            return None
        return actions[0] if len(actions) == 1 and not actions[0].get("acquisition") else None

    steps, inputs, gaps, paths = [], {}, [], {}
    ordered, seen = [], set()
    stack = [(sid, False) for sid in reversed(selected)]
    while stack:
        sid, leaving = stack.pop()
        if leaving:
            ordered.append(sid)
        elif sid not in seen:
            seen.add(sid)
            stack.append((sid, True))
            action = producer(sid)
            if action:
                stack.extend((parent, False) for parent in reversed(action["from"]))
    if set(supplied) - {sid for sid in ordered if producer(sid)}:
        raise RecordError("A supplied script must belong to an included step")
    if set(boundary) - seen:
        raise RecordError("A starting state is outside the selected dependency paths")

    def external(aid, state=None):
        item = artifacts[aid]
        filename = Path(item["name"]).name
        name = filename if portable_name(filename) else "data"
        if aid not in inputs:
            inputs[aid] = {"artifactId": aid, "stateId": state, "name": item["name"],
                           "path": f"inputs/{aid}/{name}", "sha256": item["sha256"]}
        return inputs[aid]["path"]

    for sid in ordered:
        node, action = states[sid], producer(sid)
        outputs = node.get("artifactIds", [])
        if not action:
            if (sid not in boundary and node["origin"] != "imported"
                    and not any(a.get("acquisition") for a in incoming.get(sid, []))):
                gaps.append({"stateId": sid, "message": "Producer is missing or ambiguous. Choose this artifact as a starting input or provide a recorded step."})
            if not outputs:
                gaps.append({"stateId": sid, "message": "No recorded files are available for this starting state."})
            paths[sid] = {aid: external(aid, sid) for aid in outputs}
            continue
        problems = []
        key = f"step_{len(steps) + 1}"
        paths[sid] = {}
        if action.get("origin") != "recorded" or action["status"] != "completed" or not action.get("argvTemplate"):
            problems.append("This step lacks a successful, observed command with structured arguments.")
        output_records = []
        for aid in outputs:
            name = artifacts[aid]["name"]
            if not portable_name(name):
                problems.append("An output name cannot be represented as a portable file path.")
                continue
            path = f"results/{key}/{name}"
            paths[sid][aid] = path
            output_records.append({"name": name, "path": path, "artifactId": aid, "sha256": artifacts[aid]["sha256"]})
        if not output_records or len({v["path"] for v in output_records}) != len(output_records):
            problems.append("The step needs distinct recorded output files.")
        parents_used = set()
        bindings, literals = [], {}
        for aid in action.get("inputArtifacts", []):
            item = artifacts[aid]
            if item["role"] in {"code", "environment", "log"}:
                continue
            matches = [(parent, candidate, path) for parent in action["from"]
                       for candidate, path in paths[parent].items()
                       if candidate == aid or (artifacts[candidate]["sha256"], artifacts[candidate]["sourcePath"])
                       == (item["sha256"], item["sourcePath"])]
            if len(matches) > 1 and any(candidate == aid for _, candidate, _ in matches):
                matches = [match for match in matches if match[1] == aid]
            if len(matches) == 1:
                parent, _, path = matches[0]
                parents_used.add(parent)
            else:
                if matches:
                    problems.append(f"Several upstream files match {item['name']}.")
                path = external(aid)
            token = f"{{input:{len(bindings)}}}"
            literals[item["sourcePath"]] = token
            bindings.append(path)
        if set(action["from"]) - parents_used:
            problems.append("A recorded parent has no matched file input. Record the input explicitly or revise the pipeline boundary.")
        replacement = supplied.get(sid)
        original_argv = action.get("argvTemplate", [])
        script_args = [arg for arg in original_argv[1:] if Path(arg).suffix.lower() in SCRIPT_SUFFIXES
                       and not arg.startswith("-")]
        if replacement and len(script_args) != 1:
            raise RecordError(f"{node['title']} needs a single identifiable script argument to supply a replacement")
        scripts = []
        for aid in action.get("code", {}).get("scriptArtifacts", []):
            item = artifacts[aid]
            source = Path(item["sourcePath"])
            name = source.name
            if not portable_name(name) or name in {script["name"] for script in scripts} or item["storage"] != "preserved":
                problems.append("A script cannot be bundled under a unique portable filename.")
                continue
            if source.is_relative_to(root):
                literals[str(source.relative_to(root))] = f"{{script:{len(scripts)}}}"
            literals[str(source)] = f"{{script:{len(scripts)}}}"
            scripts.append({"artifactId": aid, "name": name, "source": "recorded"})
        if replacement:
            name = replacement["name"]
            if not portable_name(name) or name in {entry["name"] for entry in scripts}:
                name = "replacement" + Path(script_args[0]).suffix
                if name in {entry["name"] for entry in scripts}:
                    raise RecordError("Choose a unique filename for the provided script")
            literals[script_args[0]] = f"{{script:{len(scripts)}}}"
            scripts.append({"artifactId": replacement["id"], "name": name, "source": "newly supplied"})
        argv = []
        for i, value in enumerate(original_argv):
            flag, equal, argument = value.partition("=") if value.startswith("--") else ("", "", value)
            mapped = literals.get(argument)
            if mapped is None and Path(argument).is_absolute():
                mapped = literals.get(str(Path(argument).resolve()))
            argument = mapped or argument.removeprefix("{run}/")
            if i == 0 and re.fullmatch(r"(?:python[\d.]*|Rscript|bash|sh|perl|julia)", Path(argument).name):
                argument = Path(argument).name
            placeholders = re.findall(r"\{input:(\d+)\}", argument)
            if (re.search(r"(?:^|[= ,])(?:/|~/|[A-Za-z]:[\\/])", argument)
                    or "{project}" in argument or "{run}" in argument
                    or any(int(index) >= len(bindings) for index in placeholders)):
                problems.append("An argument refers to a local path or an unresolved input.")
            if i > 0 and re.search(r"\.(?:py|r|sh|pl|jl|ipynb)$", argument, re.I) and not argument.startswith("{script:"):
                problems.append("A script argument has no preserved source file.")
            argv.append(flag + equal + argument)
        if argv and Path(argv[0]).name in {"sh", "bash", "zsh"} and any(re.fullmatch(r"-[a-zA-Z]*c[a-zA-Z]*", v) for v in argv[1:]):
            problems.append("Shell snippets need a preserved script with explicit file inputs and outputs.")
        if not argv:
            problems.append("No portable command is available.")
        environment = action.get("environment", {})
        steps.append({"key": key, "stateId": sid, "actionId": action["id"], "title": node["title"],
                      "evidence": action.get("origin"), "inputs": bindings, "outputs": output_records,
                      "argv": argv, "scripts": scripts, "toolVersions": environment.get("declaredToolVersions", []),
                      "stdout": environment.get("stdoutOutput")})
        gaps.extend({"stateId": sid, "message": problem} for problem in dict.fromkeys(problems))
    used = {path for step in steps for path in step["inputs"]}
    used.update(path for sid in selected for path in paths[sid].values())
    if not steps:
        gaps.append({"stateId": selected[0], "message": "The selected boundary leaves no recorded steps to replay."})
    return {"engine": engine, "targets": [{"stateId": sid, "title": states[sid]["title"],
            "paths": list(paths[sid].values())} for sid in selected],
            "boundary": boundary, "steps": steps, "inputs": [entry for entry in inputs.values() if entry["path"] in used], "gaps": gaps}
