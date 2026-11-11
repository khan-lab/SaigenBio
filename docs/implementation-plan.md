# SaigenBio implementation plan

SaigenBio helps researchers understand how an analysis branched, what each action produced, and why a human or AI chose the next step. The first working version connects the existing flow interface to durable records and actual files.

## The experience we are keeping

The canvas runs from left to right. Nodes represent saved analysis states; arrows represent commands, scripts, or planned actions. Hovering shows new outputs and a representative figure. Selecting a node opens a separate detail screen. Commands and decisions stay attached to the relevant arrows. Hovering an arrow reveals action details; hovering its label shows the associated scripts, inputs, and output files. Multiple files appear in a compact list with roles and project-relative paths or aliases for external locations. Selecting a file opens its preserved preview, and its displayed path can be copied. There are no fixed side panels or persistent canvas instructions.

Command previews abbreviate paths by default. State details provide an explicit Exact local command control. This is a display change: the original local execution records, exports, and preserved file contents remain intact.

Tool names appear above indented command options. For actions with declared metadata inputs, labels identify the source state and whether recorded metadata contents match comparable actions. Hover details distinguish changed inputs from shared metadata using file checksums; missing evidence remains unknown. Internal record IDs stay out of normal labels, while code versions remain in state details.

A running command has a short arrow that travels repeatedly along a dotted connection toward a dotted destination. It does not imply a percentage complete. Successful execution produces a solid connection and result state. Failed, cancelled, and uncertain attempts remain visible.

## Delivery order

| Stage | Work | Evidence that it works |
| --- | --- | --- |
| 1 | A project record on disk, an AI-facing execution wrapper, and real artifact previews | An agent creates a branch; the viewer displays observed execution status and preserved outputs |
| 2 | Persistent human edits through the same recorder | An annotation and layout change survive reopening; conflicting edits do not overwrite each other |
| 3 | Automatic recording of human terminal commands | Human shell actions enter the same record format without recording raw keystrokes |
| 4 | Notebook and other analysis integrations | Actual cell execution order, workflow tasks, and outputs appear through adapters |

Stages 1 and 2 are implemented. Stage 3 now has scoped interactive zsh recording with explicit saved states; hosted accounts, billing, and notebook adapters remain later work.

## Local architecture

The interface remains plain HTML, CSS, and JavaScript. A small Python service reads project records and accepts edits. The agent uses a skill and Python recorder commands. Both writers share the same storage rules.

```text
AI agent -> skill and recorder -> project history and artifacts
                                        |
                                        v
                               local HTTP service
                                        |
                                        v
                                existing flow UI
                                        |
                                   human edits
                                        |
                                        +----> project history
```

Each analysis project owns a .saigen directory:

```text
analysis-project/
  .saigen/
    project.sqlite       Current graph and append-only event history
    objects/             Preserved file bodies, addressed by SHA-256
    runs/
      run_ID/
        work/            Separate working directory for each attempt
        logs/            Standard output and standard error
```

SQLite transactions protect concurrent writes. A revision number detects stale browser edits. The service binds to the local machine. Commands run through the CLI; the browser API edits records and serves registered artifacts.

The database is the source of truth. Browser storage is not used for project history. A JSON export includes the graph and events; artifact bodies must accompany it for a complete copy. The database and generated outputs are excluded from this software repository's Git history.

## What a record means

| Question | Recorded information |
| --- | --- |
| Who | Declared writer, executor, and the source of a decision or explanation |
| When | Recorder timestamps, start, finish, and subsequent edits |
| How | Argument list, displayed command, working directory, exit status, relevant code and environment records |
| What | Parent states, declared inputs, preserved output files, logs, file hashes, and previews |
| Why | The stated purpose and later annotations, with their authors and revision history |

A state ID is independent of a Git commit. Different parameters can produce different states using the same code. The recorder stores the Git commit, tracked uncommitted diff, and snapshots of declared scripts and environment files. Actor names and supplied tool versions are declarations, not authenticated identity or automatically verified versions.

An imported file establishes that the recorder saw that file. It does not establish how the earlier analysis was executed. A planned edge is a proposal. An observed process exit establishes process status, not scientific correctness.

## Execution and artifact rules

The agent declares parent states, inputs, expected outputs, and the reason for a new action. The recorder runs the supplied argument list in a fresh working directory. Each attempt has its own output location, including retries.

Inputs can be existing paths or previously registered artifacts. Preserved input placeholders point to the recorded copies. The wrapper captures standard output and error without recording raw keystrokes or the full environment.

Success requires exit code zero and all declared output files. Output validation errors remain visible even when the process itself exited successfully. Loss of the recorder heartbeat produces an unknown status; it never implies completion. Retrying creates a new attempt from the chosen preserved parent.

Output snapshots keep earlier results available after later files change. A reference to a large external file records its hash and original path without copying it. The viewer reports missing or changed references. A hash detects change; it does not retain the old contents.

The wrapper records declared files. It is not a filesystem sandbox, an automatic dependency detector, or a guarantee that every computational dependency has been preserved.

## Human editing rules

Layout edits change positions. Notes and labels can be revised. Adding a branch creates a planned state and action; it does not run the proposed command.

Observed command arguments, exit codes, input relationships, and execution identities remain intact. Recorded actions accept an additional human annotation. The original event history is retained. Only manual plans can be removed or reconnected.

Undo appends another event and checks that the affected values have not been replaced by newer work. Stale edits return a conflict. The form remains available for the user to review and resubmit.

## Recorded shell sessions

The agreed interface is option A: retain shell activity automatically, then create a canvas state only when a human or agent explicitly saves meaningful outputs.

saigen start opens a scoped zsh session. Commands, directories, timestamps, and shell and pipeline exit statuses enter the existing event history. Temporary hooks leave user configuration files intact. The session writes no separate raw shell history.

saigen save preserves selected outputs, pending commands, recording gaps, a stated reason, and optional scripts. A checkpoint is labelled Saved. The grouping is declared by the saver and does not imply file dependencies or successful completion of every command. Git context and script snapshots describe save time.

Ordinary commands create no nodes. The viewer shows a new state after saving, with a representative selected figure and a Terminal activity section in details. Existing wrapper runs stay distinct observed executions and link to the session without duplicate shell steps.

Pause/resume controls structured capture and the optional output transcript. Basic secret detection applies to command text before storage; opt-in output transcripts remain unredacted. Background launch status is distinct from completion, and uncertain endings are not marked successful. Separate sessions retain independent heads and pending command groups.

The first shell implementation targets zsh on POSIX, tested on macOS. Child scripts and agent tools are not recursively captured. The agent skill continues to use the execution wrapper.

## First real example

Use the existing unfiltered VCF outputs in ecoli-evol as imported starting evidence. Record new depth-2 and depth-10 filtering attempts using its installed vcfutils.pl. Generate actual statistics and figures, then compare the recorded branch outputs.

Preserve the original repository and files. New work runs in a separate SaigenBio project. The example should include a failed attempt and a successful retry, with a clear explanation that they exercise the recorder rather than represent a biological finding.

The original upstream alignment and calling steps remain imported context. Their historical filter parameters and execution details must not be inferred from the current scripts.

## Acceptance checks

- Reopen the project and recover the same graph, notes, and artifact references.
- Watch a real subprocess change an action from running to completed or failed.
- Retain a failed attempt when a new attempt succeeds.
- Show a real generated figure and its source file on hover and in details.
- Preserve an earlier output after its working copy is changed.
- Reject a stale edit and preserve both the observed facts and accepted human revisions.
- Restore an edit through Undo without deleting the earlier history.
- Keep the canvas position while new records arrive.
- Treat a lost heartbeat as uncertainty.
- Preserve the existing mock as a separate illustrative reference.

## Initial implementation status

The local recorder, project API, connected viewer, artifact previews, and persistent human editing are implemented. The agent skill is bundled with the repository. The original standalone mock remains available separately.

Automated checks cover preserved artifacts, real command success and failure, missing outputs, cancellation, stale and concurrent edits, immutable execution facts, Undo, graph validation, heartbeat recovery, exports, and the HTTP artifact API. Browser checks cover file lists on edge labels, file contents, real figure previews, edits surviving reload, planned branches, Undo, and live running-to-completed updates without moving the canvas.

The ecoli example records fresh depth-2 and depth-10 results, real summary tables and figures, a failed attempt and retry, and a two-input comparison. Generated example projects are Git-ignored. The source ecoli-evol repository is not modified or committed by this implementation.

## Remaining expansion

The first version targets one local project with modest files and graphs. Later work includes resumable remote jobs, authenticated multiple-user collaboration, streaming large artifact previews, explicit decision-maker and conversation references, full dependency capture, portable restore/import tooling, broader shell adapters, and environment replay. These additions should extend the record format without replacing the canvas interaction.

## Selected-state reports (implemented)

A compact Report mode lets a researcher select multiple states sequentially. Numbered badges express presentation order, and selected states can be removed or the selection cleared or cancelled. The canvas retains its existing navigation and editing behavior outside this mode. Rendering status and PDF/source downloads appear in the temporary report controls; no permanent report panel is added.

The local service takes one fixed-revision graph snapshot and generates a Quarto/Typst PDF from selected states and their incoming action records. Saved figures lead each selected state, followed by concise recorded notes and reasons. States without figures receive explicit evidence/status context. Omitted parent titles provide context only. A compact appendix identifies scripts, input/output references and hashes. Reporting neither runs analysis nor invents a dependency order or biological interpretation.

PDF, editable QMD, controlled Quarto project configuration, actual included figures, selected snapshot and a hash manifest are saved together under `.saigen/reports/`. A downloadable ZIP packages these files. Paths are aliased in exported text; figure bytes remain exact preserved evidence. Reports do not change graph revisions or append analysis records.

Report POST and status/download endpoints retain loopback/host, same-origin and session-token protections. Only registered preserved figure objects are copied, with SHA-256 verification; external references are not opened. Recorded Markdown, fences, includes and URLs are escaped into display text. Quarto receives a fixed argument list and disabled code execution, with controlled local configuration to prevent inherited project hooks. Unsupported or missing images are disclosed. One render runs at a time, with bounded selection/file sizes and a timeout.

Checks cover ordered selection, omitted-state exclusion, immutable snapshot/figure hashes, missing/unsafe figures, inert record text, command option preservation, fixed render invocation and protected endpoints. Real preserved E. coli SVGs are rendered locally and inspected as PDF pages, and browser checks exercise selection and downloads. Current limitations include SVG/PNG/JPEG only, no full analysis replay bundle, no retained download registry across server restarts, and no publication-template customization or generated scientific prose.
