"""Shared service for future CLI, UI and MCP clients. No engine launches here."""
import copy
from ..store import RecordError, entity, now, uid, text
from . import repository as repo
from .models import document, execution_digest, canonical


class WorkflowService:
    def __init__(self, store):
        self.store = store

    def show(self, ident):
        return copy.deepcopy(repo.proposal(self.store.flow(), ident))

    def propose(self, spec, *, revision, actor="AI agent"):
        spec = document(spec)
        ident = uid("wf")
        def change(flow):
            for binding in spec["inputBindings"]:
                state = entity(flow, "states", binding["stateId"])
                if state["status"] not in {"imported", "completed", "saved"}:
                    raise RecordError("Workflow inputs must be recorded results")
                if binding["artifactId"] not in state.get("manifest", []) + state.get("artifactIds", []):
                    raise RecordError("Input artifact does not belong to its declared state")
                if binding["artifactId"] not in flow["artifacts"]:
                    raise RecordError("Unknown workflow input artifact")
            for context in spec["contextStateIds"]:
                entity(flow, "states", context)
            stage_nodes = {}
            roots = list(dict.fromkeys(b["stateId"] for b in spec["inputBindings"]))
            x = max(entity(flow, "states", i)["x"] for i in roots) + 320
            y = max((n["y"] for n in flow["states"]), default=0) + 210
            for index, stage in enumerate(spec["stages"]):
                node_id = uid("st")
                parents = [stage_nodes[k] for k in stage["dependsOn"]] or roots
                stage_nodes[stage["key"]] = node_id
                flow["states"].append({"id": node_id, "title": stage["title"], "note": "",
                    "expectedSummary": stage["expectedSummary"], "expectedFiles": stage["expectedFiles"],
                    "planParents": parents, "workflowProposal": ident, "workflowStage": stage["key"],
                    "status": "planned", "origin": "workflow-plan", "writtenBy": actor,
                    "performedBy": None, "createdAt": now(), "x": x + index * 320, "y": y,
                    "artifactIds": [], "manifest": [], "files": [], "references": []})
            proposal = {"id": ident, "spec": spec, "executionDigest": execution_digest(spec),
                "stageNodes": stage_nodes, "createdAt": now(), "writtenBy": actor, "approval": None}
            repo.collection(flow)["proposals"][ident] = proposal
            return {"proposal": copy.deepcopy(proposal)}, None
        flow = self.store.update("workflow.proposed", actor, change, revision)
        return copy.deepcopy(repo.proposal(flow, ident))

    def approve(self, ident, digest, *, revision, actor="AI agent"):
        def change(flow):
            proposal = repo.proposal(flow, ident)
            if digest != proposal["executionDigest"] or digest != execution_digest(proposal["spec"]):
                raise RecordError("Approval must match the published execution configuration")
            proposal["approval"] = {"executionDigest": digest, "at": now(), "declaredBy": actor,
                "source": "agent-or-cli-declared", "authenticatedHuman": False}
            return {"proposalId": ident, "approval": copy.deepcopy(proposal["approval"])}, None
        return repo.proposal(self.store.update("workflow.approved", actor, change, revision), ident)

    def register_run(self, ident, digest, engine_run_id, *, revision, actor="Recorder"):
        """Internal adapter boundary after an engine run is observed; never launches one."""
        text(engine_run_id, "engine run identity", 1000, True)
        run_id = uid("wrun")
        def change(flow):
            proposal = repo.proposal(flow, ident)
            if digest != proposal["executionDigest"] or digest != execution_digest(proposal["spec"]) or not proposal["approval"] or proposal["approval"]["executionDigest"] != digest:
                raise RecordError("A matching proposal approval is required")
            if any(r["engineRunId"] == engine_run_id and r["proposalId"] == ident for r in repo.collection(flow)["runs"].values()):
                raise RecordError("Engine run is already registered")
            record = {"id": run_id, "proposalId": ident, "executionDigest": digest,
                "engineRunId": engine_run_id, "registeredAt": now(), "events": {}, "stages": {}}
            repo.collection(flow)["runs"][run_id] = record
            return {"run": copy.deepcopy(record)}, None
        return repo.run(self.store.update("workflow.run_observed", actor, change, revision), run_id)

    def reconcile(self, run_id, events, *, revision, actor="Recorder"):
        """Store normalized engine evidence; phase 1 does not promote stage nodes to success."""
        if not isinstance(events, list) or not events:
            raise RecordError("Supply an evidence batch")
        normalized = copy.deepcopy(events)
        for event in normalized:
            if not isinstance(event, dict) or set(event) != {"id", "stage", "attempt", "status", "source", "artifactIds"}:
                raise RecordError("Invalid engine evidence event")
            for field in ("id", "stage", "source"):
                text(event[field], field, 20000, True)
            if type(event["attempt"]) is not int or event["attempt"] < 1:
                raise RecordError("Invalid task attempt")
            if not isinstance(event["status"], str) or event["status"] not in {"running", "completed", "failed", "cached", "skipped", "unknown", "cancelled"}:
                raise RecordError("Invalid observed task status")
            if not isinstance(event["artifactIds"], list) or any(not isinstance(i, str) for i in event["artifactIds"]):
                raise RecordError("Invalid observed artifact IDs")
        def change(flow):
            run = repo.run(flow, run_id)
            stages = repo.proposal(flow, run["proposalId"])["stageNodes"]
            for event in normalized:
                if event["stage"] not in stages:
                    raise RecordError("Evidence names an unknown proposed stage")
                if any(i not in flow["artifacts"] for i in event["artifactIds"]):
                    raise RecordError("Evidence references an unrecorded artifact")
                previous = run["events"].get(event["id"])
                if previous and canonical(previous) != canonical(event):
                    raise RecordError("Conflicting replay of an engine event")
                run["events"][event["id"]] = event
            # Store every observation. A later adapter must define aggregation and output rules.
            return {"runId": run_id, "eventIds": list(dict.fromkeys(e["id"] for e in normalized))}, None
        return repo.run(self.store.update("workflow.evidence", actor, change, revision), run_id)
