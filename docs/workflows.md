# Workflow integration foundation

SaigenBio is developing engine-independent workflow integration. The current foundation publishes workflow proposals, records declared approval, and stores normalized execution evidence through an internal service. It does **not** inspect, install, or execute Nextflow or Snakemake. There are no production engine adapters yet. Approval never launches a process.

Start from existing data and analysis context at any stage; EDA is optional. The intended interaction is: the agent prepares a concrete proposal and displays it, obtains the user's agreement, records that approval, and initiates the workflow through the integration. The engine performs computation. Users need not run the commands themselves.

## Current commands

```sh
saigen workflow engines
saigen workflow propose --spec proposal.json --revision PROJECT_REVISION
saigen workflow show PROPOSAL_ID
saigen workflow approve PROPOSAL_ID --digest EXECUTION_DIGEST --revision PROJECT_REVISION
```

Use the active project's `saigen flow` revision when saving. Supply `--project PATH` before `workflow` to choose another project. Spec file paths are relative to the invoking shell directory. Results are JSON. `workflow engines` honestly returns an empty registry and `executionSupported: false`.

`approve` declares that the user agreed to that proposal. It does not authenticate a human identity or override the agent host's permissions. A planned workflow review checkpoint still requires agreement even in Flexible mode. The agent must obtain agreement before recording approval.

## Proposal specification

The following example uses placeholders for existing recorded state and artifact IDs and pipeline identity. Replace them with observed information before publication; pipeline identity is declared at this phase and is not independently verified against source files.

```json
{
  "schemaVersion": 1,
  "engine": {"name": "nextflow", "version": "DETECTED_VERSION"},
  "pipeline": {
    "source": "/path/to/local/pipeline",
    "revision": "PINNED_REVISION",
    "contentDigest": "SOURCE_DIGEST"
  },
  "inputBindings": [
    {"name": "samples", "stateId": "EXISTING_STATE_ID", "artifactId": "EXISTING_ARTIFACT_ID"}
  ],
  "contextStateIds": [],
  "configuration": {"parameters": {}, "profile": "local"},
  "stages": [
    {
      "key": "quality",
      "title": "Read quality assessment",
      "dependsOn": [],
      "expectedSummary": "Quality summaries for the supplied samples.",
      "expectedFiles": ["quality.tsv"],
      "mapping": {"source": "agent-proposed", "taskSelectors": ["quality"]}
    }
  ],
  "limitations": ["Technical stage mapping requires review."]
}
```

Stages must be in dependency order. Input artifacts must belong to the declared recorded input states. Context states explain scientific choices and do not automatically become consumed files or data dependency edges.

Publication adds all stage placeholders and the immutable proposal in one revision. `planParents` carries proposed dependencies; no execution actions are invented. Workflow dependency drawing and a dedicated review panel are future UI work; the current canvas displays the planned cards. Approval can be reviewed through `workflow show`.

The service calculates a canonical digest over the specification, excluding generated canvas layout, notes, IDs and approval metadata. A changed specification creates a new proposal with its own approval. Existing approved proposals remain historical records and are not overwritten. Graph layout and note edits do not change the proposal.

## Evidence and compatibility

Workflow records live under an optional `workflows` field in the existing project JSON and use the recorder's SQLite transaction, revision checks, and event history. Existing projects need no rewrite. Export preserves these records with the flow.

Internal adapter-facing operations register an observed engine run and reconcile uniquely identified evidence events. Evidence is distinct from observed SaigenBio command actions. Replayed event IDs retain one observation; conflicting payloads are rejected atomically. A replay can append an audit event but never duplicates graph states or artifacts. Run identities distinguish separate engine runs, and task attempts are retained in observations.

Evidence statuses include running, completed, failed, cached, skipped, unknown, and cancelled. Foundation evidence does not promote canvas cards to completed results. A later adapter and stage mapping must verify outputs and define aggregation before doing so. An engine-reported completion without the promised artifact evidence cannot become a successful scientific result merely through reconciliation.

## Development sequence

1. Foundation: shared contract, atomic proposals, declared approval, and evidence persistence (this release).
2. Nextflow: local inspection with declared capabilities, launch identity verification, process lifecycle, task evidence and output reconciliation using a small real pipeline.
3. Workflow review UI: configuration, limitations, task evidence and progress through explicit service interfaces.
4. Snakemake: validate the same abstractions with a second engine.
5. Optional MCP and onboarding: expose the tested service without duplicating its logic.

Engine setup and downloads are deliberate choices. Inspection may evaluate pipeline code or fetch dependencies; adapters must report these requirements. Local source, schemas and documentation take priority over repeated web searches. Inspection caches must include engine version, pipeline content and configuration.

Tests and installations belong outside the source repository. Select the particular Data Carpentry example before the real Nextflow integration test; that example has not yet been agreed. No biological analysis is run by foundation tests.
