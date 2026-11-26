# Workflow adapter contract

Read [workflow integration status](workflows.md) before implementing an adapter. The registry contains local Nextflow and Snakemake adapters; engine availability is detected separately.

## Ownership

- `models.py`: strict proposal envelope, JSON validation and canonical configuration digest.
- `repository.py`: access to optional workflow collections in existing recorder snapshots.
- `service.py`: revision-checked atomic proposal, approval, observed-run and evidence operations.
- `cli.py`: argument parsing and dispatch to the service.
- `adapters/base.py`: typed engine identity, launch specification, evidence batch and protocol.
- `adapters/registry.py`: explicit engine support. No engine is installed implicitly.

Adapters do not edit SQLite, graph nodes, or approval records. They return structured results to a service. The local executor owns process supervision; the engine owns scheduling, caching and engine task retries. UI and MCP must call the same service as the CLI.

The protocol covers discovery, static inspection, launch preparation and staging, and evidence collection. Launch specs carry argument tokens, working directory, environment overrides, and evidence paths. The local executor launches the staged specification after approval and identity checks. Durable incremental cursor checkpointing is not implemented. Do not advertise a protocol definition as a functioning engine integration.

## Evidence rules

A normalized event has exactly `id`, `stage`, `attempt`, `status`, `source`, and `artifactIds`. IDs must remain stable on replay, and each immutable observation needs its own ID (including task status transitions). Namespacing with engine run identity and task identity is recommended. Task attempt must be a positive integer; source must identify the engine evidence being interpreted. Referenced artifacts must already be recorded.

`WorkflowService.register_run` and `reconcile` are internal ingestion boundaries for trusted adapters, not public commands for agents to invent execution facts. The generic evidence operations preserve observations only; local workflow execution has a separate output-verified finalization path. `register_run` requires a matching approved proposal and an observed engine run ID. It does not launch execution, revalidate local source contents, or verify that an external engine truly ran.

The initial local execution path verifies and snapshots source and inputs, captures outputs and task scripts, and preserves separate attempts. Further support needs independent task aggregation, durable cursor handling and continuous monitoring. `workflow recover` marks abandoned supervisors unknown; it does not resume collection. Keep EDA optional. Never silently convert engine task counts into a complete scientific plan.

Use deterministic synthetic evidence for foundation tests. Add real engine tests separately and label their prerequisites. A successful synthetic evidence test does not establish engine compatibility. Preserve ordinary recorder commands and existing workspace behavior.

Each adapter owns launch-file materialization in its `stage` method. `execution.py` supervises the process and commits output-verified results through the recorder. The initial finalization rules support one observed job per mapped stage. Many-job stages need explicit aggregation rules.
