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
