# Workflow adapter contract

Read [workflow integration status](workflows.md) before implementing an adapter. The current registry is deliberately empty.

## Ownership

- `models.py`: strict proposal envelope, JSON validation and canonical configuration digest.
- `repository.py`: access to optional workflow collections in existing recorder snapshots.
- `service.py`: revision-checked atomic proposal, approval, observed-run and evidence operations.
- `cli.py`: argument parsing and dispatch to the service.
- `adapters/base.py`: typed engine identity, launch specification, evidence batch and protocol.
- `adapters/registry.py`: explicit engine support. No engine is installed implicitly.

Adapters do not edit SQLite, graph nodes, or approval records. They return structured results to a service. The future executor owns process supervision; the engine owns scheduling, caching and engine task retries. UI and MCP must call the same service as the CLI.

The protocol contains `discover`, `inspect`, `prepare`, and `collect`. `prepare` returns argument tokens, working directory and evidence locations, not a shell string. `collect` returns an evidence batch and opaque cursor. The foundation does not launch these specifications or checkpoint cursors yet. Do not advertise a protocol definition as a functioning engine integration.

## Evidence rules

A normalized event has exactly `id`, `stage`, `attempt`, `status`, `source`, and `artifactIds`. IDs must remain stable on replay, and each immutable observation needs its own ID (including task status transitions). Namespacing with engine run identity and task identity is recommended. Task attempt must be a positive integer; source must identify the engine evidence being interpreted. Referenced artifacts must already be recorded.

`WorkflowService.register_run` and `reconcile` are internal ingestion boundaries for trusted adapters, not public commands for agents to invent execution facts. They currently preserve observations only. `register_run` requires a matching approved proposal and an observed engine run ID. It does not launch execution, revalidate local source contents, or verify that an external engine truly ran.

Before implementing execution, add source and input verification immediately before launch, independent task identity and stage aggregation, durable cursor handling, output capture, liveness and recovery, distinct attempts, and capability-based inspection. Keep EDA optional. Never silently convert engine task counts into a complete scientific plan.

Use deterministic synthetic evidence for foundation tests. Add real engine tests separately and label their prerequisites. A successful synthetic evidence test does not establish Nextflow compatibility. Preserve ordinary recorder commands and existing workspace behavior.
