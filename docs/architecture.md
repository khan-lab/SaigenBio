# Architecture and provenance

SaigenBio consists of **Saigen Engine** (Python), **Saigen Skills** (agent instructions and references), and **Saigen Canvas** (HTML/CSS/JavaScript). They ship in one repository and one installation. Codex, Claude Code and other external tools are the AI agents; Saigen Skills guides those tools rather than providing another agent.

## Components

```text
Researcher -> existing AI agent -> follows Saigen Skills
                       |
                       v
                      CLI --------> Saigen Engine services -> records/artifacts
                                           ^
                                           |
Researcher -> Saigen Canvas -> local HTTP API
```

The browser edits annotations and layout and requests reports. It does not execute scientific commands. The CLI executes explicitly supplied commands; it is not a sandbox or an automatic dependency detector.

Skills guide behavior, Engine enforces record integrity, and Canvas presents records and submits changes through the API. CLI and HTTP are Engine interfaces. Workspace setup is an Engine service that installs Skills and saves context. These component names do not imply separate distributions or require renaming the existing directories.

### Module map and dependency direction

| Component / area | Files | Owns |
| --- | --- | --- |
| Engine: record rules | `saigen/records.py` | Shared errors, identifiers, field validation, graph validation and plan-removal guards; no storage or transport dependencies |
| Engine: persistence | `saigen/store.py` | SQLite transactions, revisions, events, artifact capture and checked mutations; calls record rules before committing |
| Engine: execution | `saigen/runner.py`, `sessions.py`, `shell_session.py` | Observed attempts and shell checkpoints, using record rules and store transactions |
| Engine: reconstruction | `saigen/reconstruction.py` | Evidence proposals, preservation, review and archives |
| Engine: result history | `saigen/story.py` | Attributed statements, decisions, corrections, replacement links and timeline view models |
| Engine: reconstruction review | `saigen/reconstruction_review.py` | Selective state/relationship review, additive evidence acceptance and archives |
| Engine: verification | `saigen/verification.py`, `comparison.py` | Digest-bound proposals, isolated attempts and deterministic artifact comparisons |
| Engine: workflows | `saigen/workflows/` | Proposal models, approval, execution and adapters; adapters never write records directly |
| Engine: reporting | `saigen/reports.py`, `report_templates.py` | Frozen evidence and rendering; templates compose presentation without reading analysis files |
| Engine: Canvas response models | `saigen/views.py` | Derived table previews, removal capabilities and public history; display enrichment never updates stored facts |
| Engine: interfaces | `saigen/__main__.py`, `server.py` | CLI dispatch and HTTP transport/security; invoke shared services and persistence operations |
| Engine: setup | `saigen/onboarding.py`, `terminal.py`, `workspace.py` | Interview, instruction installation and workspace configuration |
| Skills | `skills/saigen-record/SKILL.md`, `references/` | Agent behavior, evidence interpretation and CLI usage |
| Canvas | `ui/` | Browser presentation, navigation and interaction through the HTTP API |

Dependencies point from interfaces to services and then to storage and record rules. `records.py` imports only the standard library; it must not import the CLI, server, storage, Canvas, or Skills. Services do not import HTTP handlers or CLI dispatch. Skills use the CLI contract; Canvas uses the HTTP contract. The existing setup interview starts the viewer through a lazy server import after setup, so Engine is not yet a fully isolated library package.

The initial dependency review identified shared rules embedded in `store.py` and derived Canvas responses built inside HTTP handlers. Those responsibilities now live in `records.py` and `views.py`. Store continues to re-export its previous record helpers so existing integrations keep the same exception classes and imports. CLI and HTTP mutations still call the same checked store/service operations; Canvas removal capabilities are descriptive and cannot bypass deletion guards. Database schema, CLI commands, HTTP response shapes, skill locations, and packaged asset paths remain compatible.

Further splitting should follow concrete maintenance needs: storage still owns artifact capture and checked edit operations, while CLI dispatch and browser coordination remain broad modules. Extract a responsibility with its callers and tests in a focused PR, preserve existing entry points, and verify the installed package before changing directories. Component naming alone is not a reason to move every file.

## Storage

Each analysis project owns:

```text
.saigen/
  project.sqlite          Graph, revisions, event history, shell sessions
  objects/                Preserved file bodies addressed by SHA-256
  runs/run_ID/work/       Isolated working directory for an attempt
  runs/run_ID/logs/       Process output
  reports/REPORT_ID/      Fixed-snapshot report and source bundle
```

SQLite transactions serialize updates. Revision checks detect stale edits. Browser storage is not the source of truth. Backups must retain both records and artifact bodies.

## States, actions, and artifacts

A state represents a meaningful saved result, imported evidence, or proposed output. Its ID is independent of a Git commit. An action records a transformation and its parent states. Artifacts record file identity, storage location, hash, role, and optional preview metadata.

| Evidence | Meaning |
| --- | --- |
| Imported file | File observed at import; upstream execution may be unknown |
| Agent proposal | Intended result and dependencies; no execution yet |
| Wrapped execution | Observed process arguments, timing, status, and declared artifacts |
| Saved shell checkpoint | Selected outputs grouped with captured shell activity |
| Annotation | An attributed explanation or decision, not a new execution fact |

Actor names, supplied versions, source URLs, and scientific reasons are declarations. Exit status and timestamps are observed by the recorder. Neither establishes scientific correctness.

Git metadata may include a commit, dirty status, tracked diff, and preserved scripts. A commit alone cannot identify uncommitted execution code.

## Execution lifecycle

run requires recorded parents and launches a command in a fresh working directory. acquire permits a root action with no parent, so the viewer shows acquisition without an incoming edge. Inputs can use preserved artifact references and explicit argument placeholders.

The recorder publishes a running state before execution. Completion requires exit code zero and all declared outputs. Failures and retries retain separate records. Missing heartbeats produce uncertainty, never inferred success.

plan publishes an expected-output state without an execution edge. run --plan reuses that placeholder after declared user approval and checks its parents. The approval flag does not authenticate or obtain approval. Manual canvas plans can also carry proposed edges; those are not execution records.

Alternative parameters should produce independently inspectable result states. A comparison consumes both alternatives. A presentation change should reuse the same underlying data.

## Preservation and previews

Preserved files are copied and addressed by hash; external references retain identity and location without retaining contents. The recorder captures declared dependencies, not every file a program reads.

The viewer prioritizes figures, then bounded CSV/TSV excerpts, then summaries. Older preserved tables can receive derived display previews without changing historical records. Display paths use aliases; original records and file contents retain their original paths.

## Editing and reports

The canvas is editable by default. Layout, labels, and notes may change, while execution facts remain attached to their attempts. Undo appends a checked inverse edit. Stale updates fail rather than overwrite newer work.

Reports use selected states from a fixed revision and preserved figures. Quarto/Typst rendering does not rerun the recorded analysis. See [report behavior and limits](reports.md).

## Boundaries

The service is intended for one local machine. Loopback and host checks restrict its HTTP exposure, and mutations and report access use session tokens. Preserved files and reports can still contain sensitive scientific or local information.

Shell capture observes top-level zsh submissions, not arbitrary child commands or notebook cells. Automatic notebook capture, remote orchestration, authenticated collaboration, and complete environment replay are not implemented.

## Responsibility ownership

| Component | Owns | Boundary |
| --- | --- | --- |
| Saigen Engine (`records.py`, `store.py`, services) | Record rules, execution facts, artifact identity, revisions and provenance | An annotation cannot manufacture an observed execution |
| Saigen Canvas (`ui/`) | Rendering, navigation, layout, plans and annotations | Scientific commands run through the CLI, outside browser rendering |
| Saigen Skills (`skills/`) | Portable instructions and supporting references | External AI agents follow guidance; host permissions still apply |
| Workspace integration (`workspace.py`) | Skill installation and workspace context | Setup preserves user choices and instructions |
| Initialization (`onboarding.py`, `terminal.py`) | Setup interview, terminal presentation and viewer settings | Reuse workspace preparation; do not duplicate recording logic |
| Reporting (`reports.py`) | Fixed-revision evidence exports | Rendering must not silently rerun scientific analysis |
| Agent host | Filesystem, network and command access | SaigenBio does not change global host permission settings |

`__main__.py` dispatches CLI requests; `server.py` translates HTTP requests into recorder operations. `views.py` builds derived Canvas responses without writing to the store. Keep validation of record invariants in shared Engine rules and services so every entry point gets the same protections. Terminal controls belong in `terminal.py`; configuration preparation and conflict detection belong in `workspace.py`.

Keep three locations distinct: a scientific workspace contains records and inputs; an installed application supplies executable code; a source checkout contains development changes. Test installations and biological analyses in external directories. A workspace's analysis permission does not identify a writable application checkout.

New workspaces save independent `permissionMode` (analysis: `ask` or `flexible`) and `uiDevelopment` (routine local UI source changes: `ask` or `allow`) choices. The default for source changes is `ask`. Existing configurations without `uiDevelopment` retain their legacy meaning: Flexible includes its previously granted routine UI development authorization. Adding agents must preserve both choices and user-maintained instructions. See [workflow permissions](agent-integrations.md#workflow-permissions).

When extending the application, identify the owner of each behavior, reuse its public operations, and verify compatibility at the affected boundary. Refactor concrete coupling when it obstructs that ownership; avoid speculative module splitting. Changes to stored facts, configuration defaults, or agent instructions require an explicit compatibility decision and relevant verification.

### UI file boundaries

The viewer uses ordered deferred scripts and no build framework:

- `geometry.js` calculates card anchors and action routes from explicit state inputs. It owns card dimensions and has no DOM or recorder access.
- `paths.js` creates presentation-only path and command formatters. The caller supplies current project context; each formatter instance owns its external-path aliases.
- `app.js` coordinates HTTP requests, application state, rendering, editing, navigation, and reports. It passes data into the geometry and formatting helpers.
- `style.css` owns visual styling; `index.html` owns the page shell and script loading order.

The helper files expose frozen `SaigenGeometry` and `SaigenPaths` namespaces. Keep their calculations independent of application globals so they can be exercised directly. Further extraction from `app.js` should introduce explicit interfaces when a feature needs independent maintenance. Include new assets in both the server route allowlist and wheel packaging, and verify the installed viewer loads them.

Report interaction is owned by `reports.js`: ordered selection, job state, polling, downloads, and report controls. Its factory receives application callbacks and exposes mode, selection position, rendering, and selection operations. Application selection and graph rendering remain coordinated by `app.js`. `api.js` owns JSON request handling and recorder error conversion; it receives a token provider rather than storing application session state. Feature modules must expose explicit operations and retain their private state inside their factory.

## Workflow integration

The optional workflow foundation uses existing recorder transactions for proposals, approval declarations and engine evidence. Adapters supply structured information and never write graph state directly. A constrained local Nextflow adapter and synchronous execution path are implemented; capability reporting documents unsupported task aggregation and live monitoring. See [workflow status and commands](workflows.md) and the [adapter contract](workflow-adapters.md) for responsibilities and implementation phases.

`ui/workflows.js` owns workflow identity, method summaries, parameter tables and evidence presentation through a read-only factory. It reads proposal/run records supplied by `app.js`; it never edits configuration or infers success.

`details.js` presents state input/output roles, method declarations, script excerpts, and expandable execution evidence. It receives formatting helpers and workflow context from the coordinator; it never runs analyses or writes records. The runner records optional `code.explanation` author declarations and validates excerpt ranges against preserved source before launching a command. Missing fields on older records remain missing.

### Report presentation

`reports.py` owns frozen record selection, artifact verification/copying, path aliasing, render jobs and source bundles. It prepares one content model shared by all report styles. `report_templates.py` owns the bundled presentation definitions and composition of inert Quarto text; it has no analysis-file access. Template identity and generated-source hashes are saved with each export. A contents preview prepares the fixed source once, and export renders that same source without consulting the live graph. `ui/reports.js` owns selection, template choice, preview invalidation and download controls.

### Historical reconstruction

`reconstruction.py` owns proposal validation, source/result preservation, evidence classifications, review transitions and rejection archives. Setup records source locations; the agent performs bounded interpretation and supplies a proposal. The CLI and token-protected HTTP review endpoint share the same service. Drafts are visible as existing evidence and are guarded from wrapped execution until accepted. Acceptance records a review decision and never changes historical commands into observed runs. Source locations are author-supplied citations; hashes identify preserved versions, not scientific correctness. Reconstruction fields remain separate from recorder execution facts.

### Result and decision history

`story.py` owns optional, revision-checked explanation declarations, append-only corrections, participant roles, evidence validation and replacement links. It prepares the What/Why/Who/When response from records and explicitly associated events, including archived work. Recorded dates and declared historical dates remain separate. Storage reserves IDs referenced by explanation history against unrelated reuse; undo can restore removed plans. Existing workspaces need no migration, and absent rationale or attribution remains absent. A replacement link does not change an execution status or perform workflow cancellation.

`ui/story.js` presents that Engine response. `details.js` retains supporting How/Where content; `app.js` coordinates fetching, explanation forms and archive navigation. CLI and HTTP explanation writes share the same service. Skills guide evidence interpretation and do not authorize execution through a story entry. See [result and decision history](result-history.md) for commands and compatibility behavior.

### Selective review and verification

Reconstruction extensions explicitly reference accepted state IDs and append reviewable evidence to existing states/actions. `reconstruction_review.py` checks endpoint acceptance, preserves accepted items and archives rejected draft items. Legacy whole-proposal commands review remaining drafts. Fingerprint versioning retains duplicate detection for older records; partial graph imports also check strong preserved-state identity. Semantic reconciliation across different excerpts remains a deliberate user/agent decision.

`verification.py` owns configuration validation, approval digests, runtime/artifact identity, attempt reservation, recovery and comparison records. `comparison.py` computes exact byte and explicitly scoped keyed numeric results without recorder writes. `verification_cli.py` provides transport; HTTP can record approval but cannot launch the command. `ui/reconstruction.js` and `ui/verification.js` present these records through explicit factories. Reports use `report_evidence.py` to select narrative, review and verification context; frozen source bundles include cited source copies within documented limits. See the [review design](reconstruction-review.md) and [verification guide](verification.md).
