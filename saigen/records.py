"""Shared record rules for Saigen Engine; independent of storage and interfaces."""
import math
import re
from datetime import datetime, timezone
from uuid import uuid4

ID = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
TERMINAL = {"completed", "failed", "cancelled", "unknown"}
class RecordError(ValueError): pass
class Conflict(RecordError): pass

def now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")
def uid(prefix):
    return prefix + "_" + uuid4().hex[:12]
def entity(flow, group, ident):
    for item in flow[group]:
        if item["id"] == ident:
            return item
    raise RecordError(f"Unknown {group}: {ident}")
def text(value, label, limit=20000, required=False):
    if not isinstance(value, str) or len(value) > limit or (required and not value.strip()):
        raise RecordError(f"Invalid {label}")
    return value
def names(value):
    if not isinstance(value, list) or len(value) > 500 or any(not isinstance(x, str) or len(x)>2000 for x in value):
        raise RecordError("Expected a list of file references")
    return value
def coordinates(item):
    for key in ("x", "y"):
        value = item.get(key, 0)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or abs(value)>1000000:
            raise RecordError("Invalid canvas position")
def plan_removal_error(flow, ident, *, removing=(), proposal=None):
    """Shared deletion guard; workflow retirement may remove its own unused stages together."""
    item = entity(flow, "states", ident)
    removing = set(removing) | {ident}
    if item["status"] != "planned" or item["origin"] not in {"manual", "agent-plan", "workflow-plan"}:
        return "Recorded execution history cannot be deleted"
    if item.get("workflowRun") or item.get("performedBy") or any(item.get(k) for k in ("artifactIds", "manifest", "files")):
        return "This plan contains execution or artifact evidence and cannot be deleted"
    workflows = flow.get("workflows", {})
    for record in workflows.get("runs", {}).values():
        if ident in record.get("stageNodes", {}).values() or any(v.get("stateId") == ident for v in record.get("stages", {}).values()):
            return "This state is used by a recorded workflow run"
    for other in workflows.get("proposals", {}).values():
        if other["id"] == proposal:
            continue
        if ident in other.get("stageNodes", {}).values():
            return "Cancel the whole unexecuted workflow proposal instead of deleting a stage"
        spec = other["spec"]
        if ident in spec.get("contextStateIds", []) or any(b["stateId"] == ident for b in spec["inputBindings"]):
            return "This state is referenced by a workflow proposal; preserve its input and context references"
    if (item.get("workflowProposal") and item["workflowProposal"] != proposal) or (item["origin"] == "workflow-plan" and not proposal):
        return "Cancel the whole unexecuted workflow proposal instead of deleting a stage"
    for other in flow["states"]:
        parents = other.get("planParents", []) + other.get("plan", {}).get("planParents", [])
        if other["id"] not in removing and ident in parents:
            return "Another state depends on this plan; remove dependent unused plans first"
    for action in flow["actions"]:
        if action["to"] != ident and ident not in action["from"]:
            continue
        if action["origin"] != "manual" or action["status"] != "planned":
            return "This state is used by a recorded execution"
        if action["to"] not in removing:
            return "Another state depends on this plan; remove dependent unused plans first"
    return None

def validate(flow):
    ids = set()
    for n in flow["states"]:
        if not ID.fullmatch(n["id"]) or n["id"] in ids:
            raise RecordError("Invalid or duplicate state ID")
        ids.add(n["id"])
        coordinates(n)
    archived = {ident for p in flow.get("workflows", {}).get("proposals", {}).values() if p.get("retirement") for ident in p["stageNodes"].values()}
    if ids.intersection(archived):
        raise RecordError("State ID belongs to a cancelled workflow proposal")
    aids = set()
    graph = {i: [] for i in ids}
    for a in flow["actions"]:
        if not ID.fullmatch(a["id"]) or a["id"] in aids or (not a["from"] and not a.get("acquisition")) or a["to"] not in ids:
            raise RecordError("Invalid action")
        aids.add(a["id"])
        if len(set(a["from"])) != len(a["from"]):
            raise RecordError("Duplicate parent")
        for parent in a["from"]:
            if parent not in ids or parent == a["to"]:
                raise RecordError("Invalid parent state")
            graph[parent].append(a["to"])
    # Iterative topological check avoids recursion limits on long projects.
    indegree = {i: 0 for i in ids}
    for children in graph.values():
        for child in children: indegree[child] += 1
    queue = [i for i in ids if indegree[i] == 0]
    visited = 0
    while queue:
        current = queue.pop()
        visited += 1
        for child in graph[current]:
            indegree[child] -= 1
            if indegree[child] == 0: queue.append(child)
    if visited != len(ids):
        raise RecordError("A connection would create a cycle")

