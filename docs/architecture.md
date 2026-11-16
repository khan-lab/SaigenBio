# Architecture and provenance

SaigenBio has a Python standard-library backend and a plain HTML/CSS/JavaScript viewer. A shared agent skill guides analysis recording; agent-specific setup only supplies instruction locations and project context.

## Components

```text
Agent or human -> CLI -> project records and preserved artifacts
                              ^
                              |
                         local HTTP server <-> browser
```

The browser edits annotations and layout and requests reports. It does not execute scientific commands. The CLI executes explicitly supplied commands; it is not a sandbox or an automatic dependency detector.

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
| Recorder (`store.py`, `runner.py`, `sessions.py`) | Execution facts, artifact identity, revisions and provenance | An annotation cannot manufacture an observed execution |
| Canvas (`ui/`) | Rendering, navigation, layout, plans and annotations | Scientific commands run through the CLI, outside browser rendering |
| Agent integration (`workspace.py`, `skills/`) | Portable instructions and workspace context | Instructions express user choices; the host enforces access |
| Initialization (`onboarding.py`, `terminal.py`) | Setup interview, terminal presentation and viewer settings | Reuse workspace preparation; do not duplicate recording logic |
| Reporting (`reports.py`) | Fixed-revision evidence exports | Rendering must not silently rerun scientific analysis |
| Agent host | Filesystem, network and command access | SaigenBio does not change global host permission settings |

`__main__.py` dispatches CLI requests; `server.py` translates HTTP requests into recorder operations. Keep validation of record invariants in the recorder so every entry point gets the same protections. Terminal controls belong in `terminal.py`; configuration preparation and conflict detection belong in `workspace.py`.

Keep three locations distinct: a scientific workspace contains records and inputs; an installed application supplies executable code; a source checkout contains development changes. Test installations and biological analyses in external directories. A workspace's analysis permission does not identify a writable application checkout.

New workspaces save independent `permissionMode` (analysis: `ask` or `flexible`) and `uiDevelopment` (routine local UI source changes: `ask` or `allow`) choices. The default for source changes is `ask`. Existing configurations without `uiDevelopment` retain their legacy meaning: Flexible includes its previously granted routine UI development authorization. Adding agents must preserve both choices and user-maintained instructions. See [workflow permissions](agent-integrations.md#workflow-permissions).

When extending the application, identify the owner of each behavior, reuse its public operations, and verify compatibility at the affected boundary. Refactor concrete coupling when it obstructs that ownership; avoid speculative module splitting. Changes to stored facts, configuration defaults, or agent instructions require an explicit compatibility decision and relevant verification.
