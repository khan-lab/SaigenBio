# Getting started

For a first run, follow this order: verify the installed command, create an empty analysis workspace, complete the setup interview, open a fresh agent session, approve one small step, and export its results. Keep the analysis workspace outside the SaigenBio software checkout.

## Check the installed command

[Install or update SaigenBio](installation.md), then check the command your terminal will run:

```sh
saigen init --help
```

The help should include --agent, --port, --permissions, --non-interactive, and --start-viewer. If it only lists --project, --actor, and --name, your terminal is using an older installed CLI. Updating the Git checkout alone does not update that installation. Follow [the missing-interview troubleshooting steps](installation.md#the-init-interview-is-missing) before continuing. Different builds can share a version number, so saigen --version alone is not enough to distinguish them.

## Open an analysis directory

For this walkthrough, choose a new, empty directory. For example:

```sh
mkdir -p ~/saigenbio-projects
cd ~/saigenbio-projects
mkdir first-analysis && cd first-analysis
```

If first-analysis already exists, stop and choose another unused name. Do not initialize the SaigenBio software checkout as an analysis project. Existing data and scripts can be imported later; no prescribed data-folder layout is required.

From that directory:

```sh
saigen init
```

In a terminal, init asks for a project name, one or more AI agents (or none), analysis permissions, permission for routine local SaigenBio UI source improvements, a viewer port, and whether to start the viewer. Review the settings before creating the workspace. Supplied flags skip their questions. Cancelling the interview leaves files unchanged.

In a supported terminal, select agents with checkboxes: Up/Down moves the cursor, Space toggles a choice, and Enter confirms. Use a to select all or n to clear all; confirming no choices skips agent setup. Other terminals ask a yes/no question for each agent. Questions use modest colors; set NO_COLOR=1 to disable color. Non-interactive output remains plain JSON.

The default name is the folder name. The interview suggests an available port starting at 8767. Open the printed viewer address and leave the terminal running; Ctrl+C stops the viewer. If you choose to start it later, run `saigen serve` from the analysis directory. It reuses the saved port.

If you decline immediate startup, the completion message says the viewer was not started and shows its saved address. Stay in the workspace directory and run the printed command when ready, for example:

```sh
saigen serve --project . --port 8768
```

The command uses your selected port. If you initialized a different directory with `--project`, the printed command uses that project's absolute path instead.

SaigenBio stores records under .saigen/, viewer settings in .saigen/viewer.json, and agent setup in saigen-workspace.json plus the selected agents' instruction and skill files. Initialization does not import data or run analysis. Existing conflicting instruction files are reported before a project is created.

For scripts or agents, use flags without an interview:

```sh
saigen init --project /path/to/analysis --name "My analysis" \
  --agent codex --agent claude --permissions flexible --ui-development ask \
  --port 8767 --non-interactive
```

Non-interactive init does not start a viewer unless --start-viewer is supplied. Without a terminal it automatically uses this non-interactive behavior. Omit --agent to skip agent setup. An explicitly chosen busy port produces an error; no existing service is stopped. See [workflow permissions](agent-integrations.md#workflow-permissions) for what flexible mode authorizes.

You can also use --project /path/to/analysis from another directory. Keep scientific projects separate from the SaigenBio software checkout.

## Open a fresh agent session

Open your selected agent in the analysis workspace, not the software checkout. Start a fresh session so it reads the generated project instructions and recording skill. The agent should resolve the project and CLI from saigen-workspace.json. No agent setup is needed if you chose none; you can use the CLI or [add an agent later](agent-integrations.md#prepare-a-workspace).

Start with a planning-only request, for example:

> Read this workspace's SaigenBio configuration and recording skill. I want to work through a small public-data tutorial. First propose a reproducible workflow and stop for approval. Do not download data or execute analysis yet. If there is no recorded input state, explain what must be acquired or imported before planned result nodes can be published. Do not create a report-only node.

An empty project has no input state for planned nodes to depend on. A plan in chat is appropriate until real input evidence is recorded. When inputs are available, planned nodes should use short result titles; the full method and prerequisites belong in their details. See [planning behavior](#plan-before-executing) and [workflow permissions](agent-integrations.md#workflow-permissions). A planning-only request means wait even in Flexible mode.

## Approve one small step

Once the plan and public source are clear, approve only its first useful step:

> Proceed with the public-data acquisition step we agreed on. Record the download and a small input summary in SaigenBio, then stop so I can inspect the evidence before further analysis. Keep any failed attempts in the history.

Inspect the saved table or figure and the recorded source before approving the next analysis. Running cards have dotted outlines and a Running label; completed results use solid outlines. For a complete scientific example, follow the [E. coli exploration tutorial](tutorials/ecoli-exploration.md).

## Export a first report

In the viewer, choose **Report**, select the input and result states you want to present, then choose **Create PDF**. Download both the PDF and source bundle when ready. PDF rendering requires Quarto; see [report requirements and limitations](reports.md).

Check that exporting adds no report-only node or analysis edges. The source bundle preserves the selected state order and project revision. Record any new scientific calculation needed for a report as a separate analysis first, then include that result in the export.

## Record your work

Choose the workflow that fits your analysis:

- **AI agent:** if selected during init, open a fresh agent session in the folder and describe your task. To add an agent later, see [Agent integrations](agent-integrations.md).
- **Existing files:** import selected evidence with snapshot; see [Recording reference](recording.md#record-existing-evidence).
- **Commands and scripts:** run them through the [execution wrapper](recording.md#record-a-new-run).
- **Human terminal session:** use [shell recording](recording.md#record-a-human-shell-session) and save meaningful checkpoints.

A file created outside the recorder does not automatically become a state. Existing files can be imported with their prior execution marked unknown.

For a worked biological example, follow the [E. coli tutorial](tutorials/ecoli-exploration.md).

## Read and edit the flow

Open the viewer address shown by serve.

- Drag the background to pan, scroll to zoom, or choose Fit.
- Click a state to select its editing controls. Drag it to rearrange the flow.
- Hover for about 650 ms, then choose **Show detail →** to inspect a state.
- Previews prioritize a figure, then a bounded CSV/TSV excerpt, then a summary.
- Hover an arrow for execution details; hover its label for related files.
- When a command uses several input states, their paths meet at a small junction with one outgoing arrow and one command label. Longer ancestor-input paths route above intermediate cards. The execution details retain every recorded input.
- Failed attempts stay available in gray. A successful retry is a separate attempt.

Edits save to the project. Notes and layout can change; recorded execution facts are retained. Unused standalone plans can be deleted, including agent-created plans; remove dependent plans first. For an unused workflow, open a stage editor and choose **Cancel workflow** to retire the entire proposal while retaining its history. Recorded attempts remain protected. Undo checks for conflicting changes and can restore deleted standalone plans when their inputs are still available; workflow cancellation cannot be undone.

## Plan before executing

Ask the agent to propose an analysis and wait for your approval. Proposed result nodes appear without execution edges. After approval, each recorded step becomes running and then completed or failed. Very short runs may finish between browser updates.

Planned and running nodes have dotted rectangular outlines, with the same size and connection points as solid result cards. The status label distinguishes "Planned" from "Running". Hover to read the expected result; choose **Show detail →** for the proposed method, prerequisites, inputs, and expected files. These descriptions remain available as the original plan once execution starts. Aligned cards connect with straight paths; cards on different rows can use curves.

Use status names such as planned, running, completed, imported, and failed when describing states. Dotted and solid describe their outlines; all nodes are rectangular. Use the Report interface to export selected results rather than adding a report-only node.

Permission to publish a plan is separate from approval to execute it. Native agent plan modes that prohibit writes may prevent canvas publication. See [permission guidance](agent-integrations.md#permissions-and-planning).

## Stop and resume

Stop the viewer with Ctrl+C. Restart it from the same workspace:

```sh
saigen serve --project .
```

The graph is stored on disk. Tell a new agent to inspect the existing flow before continuing. Rerunning init retains existing records and settings rather than repeating the interview. Use setup to add an agent.

Use `saigen serve --port NUMBER` for a one-time port override, or --port 0 to ask the operating system for a free port. If changing the saved address, update both .saigen/viewer.json and the viewer URL in saigen-workspace.json. Without saved settings, serve defaults to 8767. An occupied port never causes another service to be stopped automatically.

Keep the complete project directory, including .saigen/. See [backup and export](recording.md#inspect-and-export) and [PDF reports](reports.md).

## Restart with a fresh analysis

Use another empty directory and repeat the interview. You do not need to delete the old workspace. Keep it as an archive: .saigen/ contains its recorded history and preserved outputs.

Do not copy the old .saigen/, saigen-workspace.json, agent instruction files, or workspace-local recording skills into the new directory. Let init generate the new configuration and instructions. Reacquire the public data or explicitly import the existing evidence with its provenance described honestly.

If an older CLI already initialized your supposedly fresh folder, upgrading and rerunning init will retain that project rather than open an interview. Use another unused directory name. If you want to continue the existing project instead, [refresh its instructions](agent-integrations.md#refresh-existing-workspace-instructions) and use standalone setup deliberately.

## Bring in an existing analysis

In a directory that has not already been initialized with SaigenBio, run `saigen init` and choose **Bring in an existing analysis**. The relevant prompts look like this:

```text
Bring in an existing analysis? [y/N]: y
Existing project directory [...]: /path/to/research
Conversation or notes file (blank to finish): /path/to/conversation.md
Conversation or notes file (blank to finish): /path/to/notes.txt
Conversation or notes file (blank to finish):
```

Enter optional files one at a time, then press Enter on a blank line. Markdown, plain text, and raw Codex JSONL session files can be supplied as evidence for the agent to read. Relative paths resolve from the SaigenBio workspace, not from the existing project directory. Already initialized workspaces retain their settings and skip the interview.

You can also use flags; repeat `--history-file` for multiple files:

```sh
saigen init --existing-project . --history-file notes.md --agent codex
```

### Select a local Codex conversation

For local Codex sessions, look for files with this layout:

```text
~/.codex/sessions/YYYY/MM/DD/rollout-....jsonl
```

If you configured a different `CODEX_HOME`, look under its `sessions/` directory instead. To list candidate files without printing their contents:

```sh
rg --files --hidden "${CODEX_HOME:-$HOME/.codex}/sessions" -g 'rollout-*.jsonl'
```

Choose sessions relevant to the research project; ask your agent to check their session metadata, including working directory and date, if the filenames are unclear. Paste the selected file's actual path into **Conversation or notes file**. The interactive prompt accepts `~`, but does not expand shell variables such as `$HOME`. SaigenBio currently has no automatic Codex session discovery, selection list, or dedicated JSONL parser; the agent interprets the selected raw records. A Markdown export is not required.

For the CLI equivalent, replace the example date and filename below with a real file:

```sh
saigen init --existing-project /path/to/research --agent codex \
  --history-file "$HOME/.codex/sessions/YYYY/MM/DD/rollout-....jsonl"
```

### Review the reconstruction

Setup saves source locations without reading the analysis or executing historical commands. When initializing an existing analysis in place, it preserves existing agent instructions and appends a marked SaigenBio block. Later setup can refresh that block while keeping surrounding user text; edited blocks and conflicting skill files require a manual merge. In a fresh agent session, the recording skill offers a quick overview before deeper reconstruction, explaining the possible time and token cost. You can supply scripts, outputs and local Git evidence even without conversation history. Selected source files in a proposal are preserved in full locally; choose relevant excerpts when retaining an entire conversation is inappropriate.

The agent uses `saigen reconstruct propose --file proposal.json --revision REV` to publish evidence-linked draft cards. Inspect their details, source copies, classifications and unresolved gaps. Edit titles and notes in the normal editor. Accept or reject individual states and relationships in details. Use `saigen reconstruct accept --id ID --state STATE --revision REV` or `--connection ACTION`; omitting selectors reviews remaining draft items. Accepting a result does not automatically accept its uncertain relationships. Correct unused draft structure through rejection and a revised proposal. For later evidence or overlapping work, use an explicit extension with existing accepted IDs and reviewable additional citations; accepted evidence stays intact. Repeated evidence graphs are detected even with renamed IDs or paths; intentional alternatives also need a relation and reason. See the [proposal format](../skills/saigen-record/references/reconstruction.md). Rejected proposals remain archived.

`saigen reconstruct show` lets another session resume the review; use `--id ID` to select one reconstruction. Each entry includes the current project revision, review status, original `spec`, and a `graph` with current titles, notes and connections. For rejected proposals, the graph comes from the archive. Agents should resume from `graph`, retaining `spec` as the original submission.

Acceptance records your review and keeps historical execution unobserved. Accepted states can be inputs to new recorded runs. Drafts cannot be used in wrapped runs or as workflow input bindings. Existing results can be exported with reconstruction labels and evidence references. Optional [verification](verification.md) records a separate attempt and comparison. Large-folder discovery and automatic chat-provider ingestion remain outside this scope. Git history can support code identity but cannot alone prove historical execution.
