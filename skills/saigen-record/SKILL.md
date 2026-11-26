---
name: saigen-record
description: Record, reconstruct, or organize biological analysis in SaigenBio. Use for analysis plans, recorded execution, historical reconstruction, and grouping results on the Canvas.
---

# Record an analysis

## Acquire or import a dataset

For a user-requested download, use `saigen acquire` with the same execution options as run, but no --from. Supply --source-url for each public source, --expect for the dataset preview, and declare downloaded files and scripts. The root acquisition state has no incoming edge; its details retain the observed command, timing, status, logs, hashes, and declared source URLs. Record the real download command when it executes; do not reconstruct a download history afterward.

If useful, have the acquisition script create a compact samples.tsv alongside the data, with metadata grounded in the public source. Preserve it as an output. Plots take preview priority, then bounded CSV/TSV table excerpts, then the summary. Do not invent sample descriptions from filenames. Use `saigen annotate --project PATH --state STATE --note TEXT` to add a biological summary after inspection; this changes annotations, not execution facts.

For files already present, use snapshot and describe unknown upstream provenance honestly. A public processed table is not raw reads, and CSV depth filtering is not necessarily equivalent to a VCF tool's complete filter behavior. The user does not need to name these recording commands.

## Publish progress and plans

Give each meaningful proposed result enough context to understand on the Canvas. Record its question or purpose, the intended input states, the proposed procedure and key settings, and the expected result and files. Use the fields below. When a question or decision rationale matters beyond the procedure, append a concise `question` or `decision` with `saigen explain`. Record this context proactively as part of planning or execution without waiting for a request to document it.

When recording a wrapped run or acquisition, supply `--explanation` with a short plain-English description of the actual method, important operations, and relevant parameter values. Keep `--reason` for why the analysis is being done. When selected source lines help explain the method, use repeatable `--script-excerpt PATH:START:END` before `-- COMMAND` (1–40 lines per excerpt). Select meaningful lines, not an arbitrary prefix; the recorder preserves the script and attributes your explanation and selection. Full scripts remain available. Do not invent explanations for historical records or treat workflow-wide input bindings as observed per-stage file consumption. Workflow stages already support a declared `method.summary`; keep it specific to each stage.

For ordinary execution, provide `saigen run --expect "…"` with a brief description of the output. The wrapper publishes a running placeholder and animated incoming edge before launching the command; completion attaches actual results to that same state.

Name each planned result with a short, concrete title, usually 3–6 words. Describe the result the user will inspect, such as "Spatial QC summary" or "Spatial cluster map". Keep method names when they distinguish results. The canvas supplies the status: leave "Planned", approval reminders, and "REVIEW CHECKPOINT" out of titles.

Use `--expect` for one short sentence describing the expected result, without an "Expected:" prefix. The hover preview labels this sentence. Put the proposed procedure in optional `--details` and a condition for proceeding in optional `--requires`; these appear in the detail view. For example, describe QC plots in `--expect`, QC metrics in `--details`, and a requested review checkpoint in `--requires`. Prerequisites are descriptive text, not enforced gates or approval records. Keep the full scientific explanation in these fields or chat rather than packing it into the title or expected-result sentence.

When the user requests planning without execution, first inspect the project and import existing inputs as needed with honest provenance. Publish each proposed output with:

```sh
saigen plan --project PATH --from INPUT_STATE --id qc_plan \
  --title "Spatial QC summary" \
  --expect "QC plots and a summary of available samples." \
  --details "Inspect counts, detected genes, and tissue coverage." \
  --requires "Review QC before normalization." --output qc.svg
```

A later proposal may use an earlier planned state's ID as its --from value. This stores intended dependencies without drawing execution edges. Present the scientific plan in chat and wait for the user's approval. Publishing nodes does not execute or approve the plan. If an agent's plan mode forbids writes, provide the plan in chat and explain that canvas publication must wait until writes are allowed; never bypass that restriction.

After explicit user approval, execute one step at a time with `saigen run --plan qc_plan --approved --from INPUT_STATE … -- COMMAND`. Use actual completed parents and the planned state's exact ID. The approval flag declares approval; it does not obtain approval from the user. Keep remaining nodes planned until their respective commands start. Do not interpret a plan written in chat as automatically synchronized: use the plan command.

A failed planned execution remains a failed result. Retry through a new run rather than overwriting it. If the scientific plan changes, explain which remaining proposals are obsolete; do not execute stale proposals automatically.

## When publishing is blocked by permissions

If a planning-record write is blocked, distinguish filesystem permissions from a native plan-mode restriction. Do not infer that all writes are impossible merely because the default sandbox is read-only: a supported command approval may allow this specific operation.

When escalation is supported and the current mode permits it, request approval through the agent's normal approval mechanism for the specific planning command and any necessary input import. Explain the concrete project and effect: "May I save these planned nodes to SaigenBio? This only updates the canvas; analysis will wait for your approval." If importing input files is included, disclose that those files will also be preserved. Keep analysis commands out of this approval request.

If command approval is unavailable, ask whether the user wants to enable workspace writes. Use the host agent's documented permission controls; consult the integration guide supplied with the workspace rather than assuming any particular slash command. The agent cannot grant itself permissions or change permission configuration on the user's behalf.

If native Plan mode forbids the write, explain that limitation and ask the user to switch to a mode that permits publishing records while retaining the instruction to wait before analysis. Do not use escalation to bypass a plan-mode restriction. If a managed policy prevents the change or the user declines, leave the plan in chat and clearly state that it has not been published.

After approval or confirmation of the settings change, inspect the active project's flow before retrying, so partially published plans are not duplicated. Verify that the proposed states exist without execution edges. Permission to publish records is not approval to execute the scientific plan. Do not ask again when the necessary permission and user authorization are already in place.

## Preserve alternatives before comparing

When the user explores a different parameter, method, or preprocessing choice, create a standalone result state for that alternative before producing a comparison. Each alternative must be independently inspectable and reusable. Separate alternative generation from comparison into actual recorded executions; do not hide both inside a single combined-result node.

Choose the appropriate shared input for the alternative, not simply the most recent state in the conversation. For example, DP >= 5 and DP >= 10 filtering normally branch from the same original variant calls. Preserve each filtered table in its own state. Then record a comparison with both result states as --from parents and their preserved artifacts as inputs. Reuse an existing valid alternative rather than rerunning it just to make the graph symmetric.

A change in presentation, such as linear versus logarithmic scaling, should reuse the same preserved counts. It should not rerun filtering or imply a changed dataset. Dependencies must reflect the data actually used.

Apply this separation during planning too: propose the alternative result and the comparison as distinct nodes, with the comparison depending on both alternatives. Execute only what the user authorized; a request to try another threshold does not automatically authorize every possible comparison or plot. Avoid nodes for incidental inspections or individual explanatory sentences.

Before reporting completion, verify that each requested alternative has its own state and preserved result, and that any comparison consumes those result states. If an earlier attempt combined generation and comparison, preserve that history. Correct it through authorized separate executions or honest imports of existing evidence; never invent execution edges for operations that did not happen.

## Export reports from existing results

Treat report export as presentation of selected analysis states. Use the viewer's Report interface to choose states and export the PDF and source bundle. Do not propose a report-only planned node, or use `saigen run` just to assemble existing figures into a report: that creates an unnecessary convergence of analysis edges. Selection order, source evidence, and project revision are preserved in the export bundle without changing the analysis graph. If viewer interaction is unavailable, explain how to select the results and export them; do not fabricate a report execution record.

If preparing a report requires new calculations or scientific comparisons, record those as meaningful analysis states first, then export them with the existing evidence. Preserve report-generation executions already recorded in older projects; do not delete them or hide their dependencies merely to simplify the canvas.

## Required completion check

In a SaigenBio-managed project, a new analysis that produces results is complete only when its execution and outputs are recorded through `saigen run` in the active project. Creating a plot or table directly is not sufficient, even if the file is correct. Reading the skill does not itself record anything.

Before execution, resolve the active project from project instructions or explicit user context. An input file's location does not select the destination project. If the destination remains ambiguous, ask rather than recording into a convenient fixture project.

Inspection commands, dependency checks, and writing a script may happen outside the wrapper. Execute the script that generates analysis results through `saigen run`, declaring its inputs, script, and expected outputs. Do not generate the final result first and then use a no-op or file-copy run to imply that its computation was recorded.

Before reporting completion:
1. Read `saigen flow --project PATH` for the same active project.
2. Confirm that the returned run's state and incoming action exist, refer to the intended parents, and have a completed execution status.
3. Confirm that the expected output artifacts are attached to that state and inspect their preserved contents. A completed command with missing or invalid outputs is not a successful analysis.
4. Report the scientific result and link or identify its saved output. Say that it is recorded only after these checks. Do not claim that the browser visibly updated unless you observed it; the flow check verifies the underlying record.

If recording fails, explain that the result is not yet reflected in SaigenBio. Preserve failed attempts. For a result previously generated outside the wrapper, either rerun its actual computation through the wrapper within the user's authorized scope, or import the existing file as evidence with unrecorded execution explicitly stated. Never fabricate earlier execution history.

## Natural analysis requests

When saigen-workspace.json specifies permissionMode, follow that saved workflow preference. In `ask` mode, ask before proposed downloads and analysis runs; requested workspace edits may proceed. In `flexible` mode, requested edits, public-data downloads, and analysis runs may proceed without a separate question for each step. For SaigenBio application source changes, follow the independent `uiDevelopment` choice: `ask` requires approval and `allow` authorizes routine local UI fixes and improvements. For legacy configurations without `uiDevelopment`, flexible mode retains its earlier authorization for these UI changes; other modes require approval. Locate the source checkout before editing it; do not assume the analysis workspace or installed package is the source. Planning-only requests and explicit review checkpoints still mean wait. These instructions do not grant filesystem or network access or override host permissions; explain a blocked action honestly. Destructive changes, uploads, spending money, and work outside the authorized scope still need user approval.

When project instructions designate this recorder, apply it to requested analysis without requiring the user to mention the skill, CLI, or state IDs. Read saigen-workspace.json when present, together with project instructions, for the active project, input locations, and viewer; do not hard-code a demo path or start a duplicate viewer. If the skill or CLI is unavailable, report the missing setup instead of silently proceeding without recording.

Inspect data types and existing records before choosing a method. Resolve scientific ambiguity from the data and context where possible; ask when a material choice remains unclear. For example, low-quality bases in FASTQ reads and low-depth calls in a VCF require different operations. A sample-count table cannot support per-variant depth filtering.

Record meaningful analysis steps within the user's scope. If the user asks to inspect QC before deciding what comes next, stop at that checkpoint. Do not extend the pipeline automatically. Import existing input evidence with honest provenance, then record new transformations and figures through the wrapper. Keep alternatives as separate attempts with the actual changed options visible in labels and commands.

Keep the user-facing conversation about the scientific question, results, and next decision. Recording mechanics belong in the saved details unless setup or recording fails.


Use the installed `saigen` CLI from the user's analysis workspace. Check `saigen --version` and use `saigen SUBCOMMAND --help` for available options. The source repository is not required. Select the analysis project explicitly with `--project PATH`; keep generated data and trials in that workspace, not in the installed skill folder.

Initialize with `saigen init --project PATH --name NAME`. View it with `saigen serve --project PATH --port PORT`, choosing a free port without stopping an unrelated viewer. If the CLI is missing, report the missing dependency instead of assuming a source checkout is available.

For a recorded action, the command shape is:

```sh
saigen run --project PATH --actor "AI agent" \
  --from STATE --title TITLE --label LABEL --reason REASON \
  --input artifact:ID --output figure.svg --script scripts/plot.py \
  -- python3 "{project}/scripts/plot.py" "{input:0}" figure.svg
```

Adapt the script, arguments, and outputs to the authorized task. `--script` and ordinary input paths resolve against the analysis project; output paths resolve against the isolated run directory. Use `saigen flow --project PATH` to obtain actual state and artifact IDs. `snapshot --file PATH` imports files into a starting state.

The recorder supports authorized analysis work; using this skill does not authorize additional experiments, uploads, or changes to unrelated projects.

- Inspect `flow` before choosing parent states. Use preserved inputs from imported or completed states. A Git commit is a code reference, not a state ID.
- Import existing evidence with `snapshot`. Explain which upstream execution details are unknown. Do not reconstruct an observed command from a current script alone.
- Use `run` for a new action. Declare the parent state, a short title and arrow label, the reason, input files, and expected outputs. Record an unknown reason as unknown rather than inventing a rationale.
- Use `--input artifact:ID` for preserved prior files and `{input:0}` in command arguments to read the recorded copy. Commands run in their own fresh working directory.
- If `--from` is omitted, exact artifact IDs with unique owning results establish the proposed parents. In Ask mode, show the researcher those parents and ask for agreement to the connections and run before passing `--approved`. The recorder blocks the run and shows the inferred parents if confirmation is missing. If the researcher declines, stop and clarify the inputs. In Flexible mode, use a unique owner automatically when the run is already within scope. If ownership is ambiguous in either mode, ask the researcher and supply the chosen owner with `--from`.
- Declare relevant scripts and environment files with `--script` and `--environment`. Set `--source-repo` when code lives elsewhere. Supplied tool versions and actor names are declarations.
- Let the wrapper determine execution status. Do not claim success from a planned edge, an animation, a current file name, or exit code zero alone. Inspect the recorded files and logs before interpreting results.
- Keep a failed attempt. A retry is a new run from an appropriate preserved parent, with its changed command or rationale made explicit.
- Repeat `--from` for a comparison that depends on more than one state.
- Do not write the SQLite database or edit recorded execution facts directly. The recorder owns process facts; the viewer adds annotations and manual plans.

The recorder captures declared files and the launched command. It does not automatically capture every tool call, conversation, or dependency.

## Recorded human sessions

`saigen start --project PATH --from "Unique state title"` opens an interactive zsh with command capture. Omit --from in an empty project. Only top-level submissions are observed; launching an agent inside it does not capture the agent’s internal tools.

- Continue using `saigen run --actor "AI agent"` for agent analysis actions. Runs in a recorded session link without duplicate shell nodes. Do not start an interactive session from an unattended agent tool invocation.
- A human can run ordinary commands and use `saigen save --title TITLE --output FILE --reason REASON` to preserve meaningful results. Each save groups pending activity. It is a captured checkpoint, not verified successful execution or proof of file dependencies.
- Save paths are relative to the current shell directory. Declare scripts with --script; scripts and Git context are captured at save time.
- Use pause/resume as separate shell submissions for private activity. Command redaction is limited; optional output transcripts are unredacted.
- A successful wrapped run becomes the next starting state. Use --from to branch elsewhere; this selects a record, not a filesystem checkout.


## Existing workflow pipelines

Start from existing data and analysis context; EDA is optional. For pipeline requests, inspect `saigen workflow --help`, `workflow engines`, and local source with `workflow inspect --engine nextflow --source PATH` before searching the web. Static inspection does not resolve a task DAG. The first adapter supports local pipeline directories and one observed task per mapped stage; do not claim general nf-core, resume or many-sample stage support.

Publish the concrete configuration and stage mappings with `workflow propose`, inspect `workflow show`, and obtain the user's agreement. Record that agreement with `workflow approve` using its digest and current project revision, then initiate `workflow execute` with the new revision. Approval never runs the pipeline by itself. Flexible mode still respects this explicit workflow review checkpoint. The user need not enter these commands; the agent performs them after agreement. Changing source, engine version, inputs or configuration requires inspection and a matching new proposal. Do not amend launch parameters outside the approved proposal.

Execution is foreground and stage cards finalize at engine exit. Check `workflow status`, recorded output contents, and failure/unknown states before claiming success. `workflow recover` can mark lost-supervisor runs unknown; it cannot infer completion. Unsupported dynamic, cached or multi-task mappings must be reported honestly rather than replaced with invented stage success. Engines and dependencies are installed only within the user's authorized scope; SaigenBio does not install them automatically.

## Explain results and decisions

After inspecting the preserved outputs, use `saigen story STATE_ID` to check what is already recorded. For a meaningful result, proactively save the main supported finding with `saigen explain`, citing a specific table, figure, or event where available. Record interpretation and material limitations separately when supported. Skip empty sections and avoid repeating the command, file list, or timestamps that SaigenBio already captures. If the result is uncertain or the attempt failed, describe what the evidence establishes and leave unsupported conclusions absent.

Keep method explanations educational. Explain what the command or key lines do in terms of the inputs, transformation, and outputs. Include the settings that matter to the result and why they were chosen when that rationale is known. Cite the source when recording a historical claim or a user's decision. Use the [result and decision reference](references/story.md) for evidence citations, participant roles, corrections, and replacement links. These records do not grant execution permission.

## Organize analysis groups

Read the active project and CLI from `saigen-workspace.json`. Inspect `saigen flow` for state IDs and dependencies and `saigen groups show` for the saved arrangement. Review both at the same project revision. Propose a hierarchy using the researcher's preferred depth and membership. Show the nesting, name the member results, explain the rationale, and point out shared or ambiguous results to leave outside. A state can be assigned directly to one group and will also appear under its ancestors. Preserve unrelated groups and use existing states and connections.

Discuss and refine the grouping before saving. After the researcher agrees, pass the complete list to `saigen groups save --file groups.json --revision REV` using the reviewed revision. Each object has `id`, `title`, direct `stateIds`, and optional `parentId` and `reason`. A parent may have an empty `stateIds` list when its descendants contain states. Use stable group IDs for revisions. On a revision conflict, re-read the groups and states and resolve changes with the researcher before saving. Verify the final hierarchy and point them to the Canvas overview.

## Bring in an existing analysis

For selected Codex JSONL conversations, follow [Reading selected Codex JSONL sessions](references/reconstruction.md#reading-selected-codex-jsonl-sessions) to interpret messages and tool records and cite their original locations.

On a reconstruction request, inspect `saigen reconstruct show` for saved drafts or accepted work. An empty result is normal before the first proposal. To start a draft or add evidence, follow [Choose evidence](references/reconstruction.md#choose-evidence). If existing-project setup is pending and the user has not asked for reconstruction, offer it without starting discovery. Resume an existing review from the recorded graph.

Use selected material together. Record local Git commit IDs as evidence of code availability, not proof that a version produced a file. Keep discovery bounded; ask about ambiguous or large scopes before deeper reading. Do not upload evidence, install software or rerun analyses as part of reconstruction. Full selected source files supplied in a proposal are copied into the local artifact store: explain that scope before including unrelated or sensitive chat exports. Choose relevant excerpts as separate source files when appropriate, with original source locations noted.

Publish a JSON proposal using `saigen reconstruct propose --file proposal.json --revision REV`. See the bundled [reconstruction reference](references/reconstruction.md) for the format. Every state and connection needs evidence classified as direct, reported, inferred or unresolved. Preserve ambiguity and conflicting source statements. Commands in a proposal are reported text and are never executed. Draft cards appear on the canvas with state, relationship and additional-evidence review controls. Accept useful states independently; an uncertain relationship may remain draft or be rejected. Omitted selectors review only remaining draft items. Follow the reference for explicit extensions that reuse accepted IDs and append later evidence rather than copying or overwriting accepted work. Users may correct titles/notes through the editor; revise evidence or structure by rejecting the draft and proposing a corrected version with new IDs and a `relation` identifying the rejected proposal, kind `revision`, and reason. Intentional alternatives use kind `alternative` and a reason. Repeated evidence graphs are blocked even with fresh IDs. Inspect existing reconstructions before importing again.

After the user reviews the complete proposal, use `saigen reconstruct accept --id ID --revision REV` or the UI review control. This records acceptance, not observed historical execution. Accepted imported states can be parents for ordinary recorded runs. For an authorized verification rerun, follow the [verification reference](references/verification.md): publish concrete preserved inputs/code and comparison criteria, obtain agreement, record digest-bound approval, then execute and inspect the separate attempt/comparison. Retain originals; matches do not establish historical identity or scientific correctness. Rejected drafts remain archived in the reconstruction record. `reconstruct show` is the durable handoff for another agent: resume from each entry's `graph` (current records, or archived records after rejection), review status and `projectRevision`. The original `spec` remains unchanged and must not override user edits shown in `graph`.

## Export a pipeline from recorded results

Use the active workspace and agent session. If the researcher supplies IDs with `$saigen-pipeline` or `/saigen-pipeline`, resolve each exact ID against `saigen flow`. Confirm the matching titles and statuses in the proposal, particularly when titles look alike. Ask about IDs that are missing, stale, or refer to a group. If targets are missing, ask the researcher to select the final result nodes on the Canvas and use **Copy node IDs**, then paste the IDs in chat. Resolve any targets identified by name and clarify ambiguity before proceeding. Determine the session reference once and reuse it throughout. Codex can use `CODEX_THREAD_ID`. On hosts that do not expose an ID, declare a stable unique reference for this conversation and pass it as `--agent-session SESSION`.

For an existing Canvas handoff, read it with `saigen pipeline wait ID` after the researcher selects nodes and clicks **Use selected results**. If they cancel, close the pending request with `saigen pipeline cancel-request ID --revision REV`.

Use `saigen pipeline propose --selection ID --engine nextflow --revision REV` once the request is ready, or use one or more `--target STATE` options for identified targets. Pass the same `--agent-session SESSION` when the host does not supply it. Repeat `--start-from STATE` to treat upstream results as supplied input files. Show concrete targets, required inputs, included steps, argv settings, evidence gaps, and engine. A revised boundary, engine, or script needs a new proposal. Use `--provide-script STATE=PATH` for a replacement with the same recorded input/output interface. Identify the newly supplied code during review. For an unresolved gap, discuss choosing an existing artifact as an input or exporting an incomplete draft. Preserve the recorded scientific defaults. Discuss changes such as making a single-sample workflow run over multiple samples.

Wait for the researcher to explicitly agree to the exact proposal in this agent session. Use the configured CLI and analysis project from `saigen-workspace.json`. Read the reviewed proposal with `saigen pipeline show "$proposal_id" --project "$project"`. Fill `proposal_id`, `digest`, and `revision` from its `id`, `digest`, and current `revision`. The `sourceRevision` identifies the recorded graph used to build the proposal. Use the researcher’s declared name and the same agent session reference used for review.

```sh
saigen pipeline approve "$proposal_id" --project "$project" \
  --digest "$digest" --researcher "$researcher" \
  --agent-session "$agent_session" --revision "$revision"
```

Add `--draft` only when the researcher approved an incomplete draft. Use the `revision` returned by the successful approval as `approved_revision`:

```sh
saigen pipeline generate "$proposal_id" --project "$project" --revision "$approved_revision"
```

If the CLI reports a revision conflict, read the proposal again. Continue only if the reviewed digest and approval state still match the intended operation. If an approval or bundle already exists, inspect it with `pipeline show` before retrying. Give the researcher the bundle location and status. Obtain a separate decision before any test or execution, and record any approved attempt separately from the original analysis.
