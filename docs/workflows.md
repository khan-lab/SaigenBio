# Workflow integration foundation

SaigenBio is developing engine-independent workflow integration. The current foundation publishes workflow proposals, records declared approval, and stores normalized execution evidence through an internal service. Local Nextflow and Snakemake adapters support static source inspection and synchronous execution of explicitly mapped stages with one observed job per stage. Engines are installed separately. See [local Nextflow](nextflow.md) and [local Snakemake](snakemake.md) for their supported configuration. Approval never launches a process.

Start from existing data and analysis context at any stage; EDA is optional. The intended interaction is: the agent prepares a concrete proposal and displays it, obtains the user's agreement, records that approval, and initiates the workflow through the integration. The engine performs computation. Users need not run the commands themselves.

## Current commands

```sh
saigen workflow engines
saigen workflow propose --spec proposal.json --revision PROJECT_REVISION
saigen workflow show PROPOSAL_ID
saigen workflow approve PROPOSAL_ID --digest EXECUTION_DIGEST --revision PROJECT_REVISION
```

Use the active project's `saigen flow` revision when saving. Supply `--project PATH` before `workflow` to choose another project. Spec file paths are relative to the invoking shell directory. Results are JSON. `workflow engines` reports each adapter, the detected engine version, and whether it supports local execution. `executionSupported` describes the implemented feature; engine availability is reported separately.

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

Publication adds all stage placeholders and the immutable proposal in one revision. `planParents` carries proposed dependencies; no execution actions are invented. The canvas displays planned cards with workflow identity and method context. Clicking a workflow label opens the saved proposal parameters and evidence. Drawing proposed workflow dependencies and an interactive approval control remain future work; agents record approval through the CLI.

The service calculates a canonical digest over the specification, excluding generated canvas layout, notes, IDs and approval metadata. A changed specification creates a new proposal with its own approval. Existing approved proposals remain historical records and are not overwritten. Graph layout and note edits do not change the proposal.

## Cancel an unused proposal

Open a planned workflow stage's editor and choose **Cancel workflow**, supplying a reason. This retires the whole proposal and removes all its planned cards from the active canvas. The agent can perform the same operation through the CLI:

```sh
saigen workflow cancel PROPOSAL_ID --revision PROJECT_REVISION --reason "Replaced by another approach"
saigen workflow show PROPOSAL_ID
```

Cancellation is allowed only before any run is recorded and when no external plan, action, or workflow context depends on the stages. Otherwise the service explains the blocking reference. Historical proposal context also remains protected. Individual workflow stages cannot be deleted through generic canvas edits.

The original specification, stage mapping, approval declaration, stage snapshots, reason and actor remain in the project and exported history. Cancelled stage IDs stay reserved. The proposal cannot be approved again, registered with a run, or executed. Cancellation is not an undoable canvas edit; publish a new proposal if you want to proceed later. Once execution has been recorded, including failed or uncertain attempts, its cards and history remain protected. This operation does not stop a running engine.

Cancellation uses an optional `retirement` record on the existing proposal; older proposals without it remain active with no migration. UI removal options are derived from recorder/service rules by the HTTP server and are never stored as analysis facts.

## Evidence and compatibility

Workflow records live under an optional `workflows` field in the existing project JSON and use the recorder's SQLite transaction, revision checks, and event history. Existing projects need no rewrite. Export preserves these records with the flow.

Internal adapter-facing operations register an observed engine run and reconcile uniquely identified evidence events. Evidence is distinct from observed SaigenBio command actions. Replayed event IDs retain one observation; conflicting payloads are rejected atomically. A replay can append an audit event but never duplicates graph states or artifacts. Run identities distinguish separate engine runs, and task attempts are retained in observations.

Evidence statuses include running, completed, failed, cached, skipped, unknown, and cancelled. Generic evidence ingestion does not promote canvas cards to completed results. The local execution path verifies job evidence and promised outputs before completing its mapped cards. An engine-reported completion without the promised artifact evidence cannot become a successful scientific result merely through reconciliation.

## Development sequence

1. Foundation: shared contract, atomic proposals, declared approval, and evidence persistence (this release).
2. Nextflow: initial local single-task-stage support is implemented; broaden task aggregation and monitoring after the constrained integration is reviewed.
3. Workflow review UI: configuration, limitations, task evidence and progress through explicit service interfaces.
4. Snakemake: local execution for one observed job per mapped rule is implemented.
5. Optional MCP and onboarding: expose the tested service without duplicating its logic.

Engine setup and downloads are deliberate choices. Inspection may evaluate pipeline code or fetch dependencies; adapters must report these requirements. Local source, schemas and documentation take priority over repeated web searches. Inspection caches must include engine version, pipeline content and configuration.

Tests and installations belong outside the source repository. Select the particular Data Carpentry example before the real Nextflow integration test; that example has not yet been agreed. No biological analysis is run by foundation tests.

## Find a published workflow for your data

Ask your agent “Is there a published workflow I can use from here?” or invoke `$saigen-find-workflow` in Codex or `/saigen-find-workflow` in Claude Code or OpenCode. Describe your goal and inputs, or select results on the Canvas and paste their IDs using **Copy node IDs**. If the shortcut is missing, [refresh your agent instructions](agent-integrations.md#refresh-existing-workspace-instructions).

The agent recommends a versioned workflow in chat and explains how it fits your existing inputs, what else it requires, what it produces, and whether SaigenBio can track that configuration. Ask to see the chosen workflow on the Canvas when you're ready to review it. For supported workflows, the agent publishes planned stages and waits for approval of the specific proposal before running it.

## Export selected Canvas results as a pipeline

Select your final result nodes on the Canvas. Shift-click or use Shift+Space to add nodes to your selection. You can also choose **Select nodes** inside a group and click or tap each result. Click **Copy node IDs**, then paste the IDs with `$saigen-pipeline` in Codex or `/saigen-pipeline` in Claude Code or OpenCode. Say whether you want Nextflow or Snakemake. If the shortcut is missing or still asks you to use the older chooser, [refresh your agent instructions](agent-integrations.md#refresh-existing-workspace-instructions).

If an agent already opened a selection request, you can select the results on the Canvas and click **Use selected results** in the request banner. Choose the request identified in chat if more than one is pending.

The agent traces recorded file inputs and proposes a workflow in Nextflow or Snakemake. You can choose an intermediate result as the starting point and use its artifact as an input. Review the concrete steps, parameters, inputs, outputs, and gaps in chat. The agent records your explicit agreement to the reviewed proposal before generating the bundle. The agreement records the declared agent session and researcher.

The bundle is saved under `.saigen/pipelines/` in the project. It includes the workflow, captured scripts, recorded command settings, required input paths, and a manifest linking the export to source state/action IDs and the reviewed project revision. Materialize the inputs at the paths in the README and install the recorded tools before running. The first exporter supports replay of explicit file-based commands with structured arguments and preserved or supplied scripts. Steps with unresolved inputs, unsupported command evidence, or missing scripts can be exported as an agreed incomplete draft. Execution and any comparison with the original artifacts are separate work.

The agent-facing `saigen pipeline` commands include `request` and `wait` for the Canvas handoff, followed by `propose`, `approve`, and `generate`. They are distinct from `saigen workflow`, which handles importing and executing existing workflows.
