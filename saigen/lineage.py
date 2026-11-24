"""Resolve exact artifact IDs to the states that own them."""
from collections import defaultdict
import json
from pathlib import Path

from .records import RecordError


def _usable(state):
    return (state["status"] in {"completed", "saved", "imported"}
            and state.get("reconstruction", {}).get("review") != "draft")


def permission_mode(root, cwd=None):
    """Use the active workspace preference when it points at this project."""
    workspace = (cwd or Path.cwd()).resolve()
    for directory in dict.fromkeys((workspace, *workspace.parents, root)):
        path = directory / "saigen-workspace.json"
        try:
            config = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            continue
        except (ValueError, UnicodeError) as exc:
            if directory == root:
                raise RecordError("Invalid SaigenBio workspace configuration") from exc
            continue
        if not isinstance(config, dict) or not isinstance(config.get("project"), str):
            continue
        if (directory / Path(config["project"]).expanduser()).resolve() == root:
            return config.get("permissionMode", "ask")
    return "ask"


def artifact_owners(flow):
    owners = defaultdict(list)
    for state in flow["states"]:
        for aid in dict.fromkeys(state.get("artifactIds", [])):
            owners[aid].append(state)
    return owners


def run_lineage(flow, parents, explicit_artifacts, *, ask=False, approved=False):
    if parents and not explicit_artifacts:
        return parents, []
    owners = artifact_owners(flow)
    bindings, inferred = [], {}
    for aid in dict.fromkeys(explicit_artifacts):
        matches = owners.get(aid, [])
        if parents:
            matches = [state for state in matches if state["id"] in parents]
        if len(matches) > 1:
            options = ", ".join(f'{state["title"]} ({state["id"]})' for state in matches)
            raise RecordError(f"Artifact {aid} has several recorded owners: {options}. Choose its owner with --from.")
        if matches:
            state = matches[0]
            if not parents and not _usable(state):
                raise RecordError(f'{state["title"]} is not an accepted, usable input result.')
            bindings.append({"artifactId": aid, "stateId": state["id"]})
            inferred[state["id"]] = state["title"]
    if parents:
        return parents, bindings
    if not inferred:
        raise RecordError("A run needs --from or an artifact input with a recorded owning result. Use acquire for a root download.")
    if ask and not approved:
        links = ", ".join(
            f"{inferred[b['stateId']]} ({b['stateId']}) supplies "
            f"{flow['artifacts'][b['artifactId']]['name']} ({b['artifactId']})"
            for b in bindings
        )
        raise RecordError(f"Confirm these input connections and the run with the researcher: {links}. Then retry with --approved.")
    return list(inferred), bindings


def legacy_actions(flow):
    """Recover supported missing links for display/export on detached actions."""
    owners = artifact_owners(flow)
    parents = defaultdict(set)
    for action in flow["actions"]:
        parents[action["to"]].update(action["from"])
    actions = []
    for action in flow["actions"]:
        # Workflow adapters may list pipeline-wide inputs on each stage.
        if ("fileInputBindings" in action or action.get("origin") != "recorded"
                or action.get("acquisition") or action.get("workflowRun")):
            actions.append(action)
            continue
        source_ids = list(action["from"])
        recovered, added = [], set()
        for aid in dict.fromkeys(action.get("inputArtifacts", [])):
            matches = owners.get(aid, [])
            if len(matches) != 1:
                continue
            owner = matches[0]
            sid, target = owner["id"], action["to"]
            recorded_at = action.get("startedAt")
            source_at = flow["artifacts"].get(aid, {}).get("capturedAt") or owner.get("finishedAt") or owner.get("createdAt")
            if not _usable(owner) or (recorded_at and source_at and source_at > recorded_at):
                continue
            if sid not in source_ids:
                seen, stack = set(), [sid]
                while stack:
                    state = stack.pop()
                    if state not in seen:
                        seen.add(state)
                        stack.extend(parents[state])
                if target in seen:
                    continue
                source_ids.append(sid)
                parents[target].add(sid)
                added.add(sid)
            if sid in added:
                recovered.append({"artifactId": aid, "stateId": sid})
        actions.append({**action, "from": source_ids, "recoveredFileInputBindings": recovered}
                       if recovered else action)
    return actions
