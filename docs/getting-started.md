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

In a terminal, init asks for a project name, one or more AI agents (or none), analysis permissions, a viewer port, and whether to start the viewer. Review the settings before creating the workspace. Supplied flags skip their questions. Cancelling the interview leaves files unchanged.

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
  --agent codex --agent claude --permissions flexible \
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
- Shift-click to add or remove nodes from the selection. Drag any selected node without Shift to move the selected group together; the group keeps its relative spacing. Shift-drag does not move nodes.
- Click empty canvas or press Esc to clear selection. With a node focused, Shift+Space toggles its selection; Enter or Space still opens its preview. Multiple selection shows a count instead of single-node edit, branch, or connect controls.
- Hover for about 650 ms, then choose **Show detail →** to inspect a state.
- Previews prioritize a figure, then a bounded CSV/TSV excerpt, then a summary.
- Hover an arrow for execution details; hover its label for related files.
- When a command uses several input states, their paths meet at a small junction with one outgoing arrow and one command label. Longer ancestor-input paths route above intermediate cards. The execution details retain every recorded input.
- Failed attempts stay available in gray. A successful retry is a separate attempt.

Choose **Auto-arrange** to lay out the visible Canvas by its dependencies. With collapsed groups, it arranges the group cards and visible results together. SaigenBio saves those positions for that overview. Expand the groups to return to the detailed result positions. Each arrangement saves as one edit, and **Undo** restores the previous layout.

Drag a card to arrange the canvas. Temporary alignment guides appear as it snaps into a row or column with nearby cards. Hold **Option** on Mac or **Alt** on other keyboards to position it freely. Press **Esc** to cancel the drag, or choose **Undo** after dropping the card.

Group moves snap using the dragged card against unselected cards and save as one edit; Undo restores the whole group's positions. Selection and layout do not change recorded dependencies or evidence. Report mode has its own ordered selection: clicking nodes, including Shift-clicking, retains the report's normal add/remove behavior rather than selecting a movement group.

Edits save to the project. Notes and layout can change; recorded execution facts are retained. Unused standalone plans can be deleted, including agent-created plans; remove dependent plans first. For an unused workflow, open a stage editor and choose **Cancel workflow** to retire the entire proposal while retaining its history. Recorded attempts remain protected. Undo checks for conflicting changes and can restore deleted standalone plans when their inputs are still available; workflow cancellation cannot be undone.

## Organize the Canvas

Ask your agent “Organize this canvas by cell type,” or invoke `$saigen-organize` in Codex or `/saigen-organize` in Claude Code or OpenCode. Choose how broadly or finely to group the work. For example, use **HeLa cell analysis** as a top-level group with **Quality control** and **Modeling** inside it, and leave shared preprocessing outside. Review the proposed hierarchy, members, and rationale in chat. The agent saves it after you agree. Ask it to revise the arrangement as the analysis changes.

The Canvas collapses top-level groups at 55% zoom or lower and expands them at 65% or higher. It keeps the previous view in between. Deeper groups expand at higher zoom levels. Click a summary card to inspect its next layer. Zoom out to its collapse threshold to return to the overview. If you open a group while already below its threshold, the next zoom-out action collapses it. Click a summary connection to inspect the original dependencies. Report selection shows individual results.

Each state can be assigned directly to one group or remain ungrouped. A group can hold results, subgroups, or both. Its summary counts results across all descendants and shows running and failed counts when applicable. Archiving or deleting a state removes its membership, and groups with no results anywhere under them disappear. Grouping leaves the original positions, states, actions, and artifacts intact.

The agent uses `saigen groups show` to read the saved groups and project revision. To save an agreed arrangement from a terminal, put the complete list in a JSON file such as `groups.json`:

```json
[
  {
    "id": "hela",
    "title": "HeLa cell analysis",
    "stateIds": []
  },
  {
    "id": "hela_modeling",
    "parentId": "hela",
    "title": "Modeling",
    "stateIds": ["hela_counts", "hela_model"],
    "reason": "Inputs and outputs of the HeLa modeling branch."
  }
]
```

Run `saigen groups save --file groups.json --revision REV` with the revision you reviewed. An empty list clears the grouping. These commands store the Canvas organization, and the agent shortcut guides the conversation that produces it. See [how to refresh older workspace instructions](agent-integrations.md#refresh-existing-workspace-instructions).

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

### Start reconstruction in your agent

Open your agent in the SaigenBio workspace. In Codex, invoke the `$saigen-reconstruct` skill. In Claude Code or OpenCode, enter `/saigen-reconstruct`. In any configured agent, you can ask “Reconstruct this project on the SaigenBio canvas.” See [how to refresh an older workspace](agent-integrations.md#refresh-existing-workspace-instructions) if the shortcut is missing.

If you supplied history files during setup, the agent offers those paths first. Otherwise, Codex can suggest local sessions by matching their original working directories to the workspace, existing analysis directory, or their Git roots. The agent shows dates and paths before opening transcripts. Choose one, several, or none, and confirm what project files or Git history to review. You can also give the agent a path manually or continue with project files alone. For a broad review, the agent can offer a smaller starting scope and explain the possible time and token cost.

You can list the same candidates directly with `saigen reconstruct sources --agent codex` from the workspace. This checks metadata headers in recent local Codex session files. With a large history, older sessions may need to be selected manually. The other agents use configured or manually supplied paths.

### Supply a local Codex conversation manually

For local Codex sessions, look for files with this layout:

```text
~/.codex/sessions/YYYY/MM/DD/rollout-....jsonl
```

If you configured a different `CODEX_HOME`, look under its `sessions/` directory instead. To list candidate files without printing their contents:

```sh
rg --files --hidden "${CODEX_HOME:-$HOME/.codex}/sessions" -g 'rollout-*.jsonl'
```

Choose sessions relevant to the research project. Give the selected file's path to your agent, or paste it into **Conversation or notes file** during setup. The interactive setup prompt accepts `~`. Use a literal path in the prompt, since it does not expand shell variables such as `$HOME`. The agent can interpret the selected raw JSONL after you confirm it.

For the CLI equivalent, replace the example date and filename below with a real file:

```sh
saigen init --existing-project /path/to/research --agent codex \
  --history-file "$HOME/.codex/sessions/YYYY/MM/DD/rollout-....jsonl"
```

### Review the reconstruction

Setup saves source locations without reading the analysis or executing historical commands. When initializing an existing analysis in place, it preserves existing agent instructions and appends a marked SaigenBio block. Later setup can refresh that block while keeping surrounding user text; edited blocks and conflicting skill files require a manual merge. In a fresh agent session, the recording skill offers a quick overview before deeper reconstruction, explaining the possible time and token cost. You can supply scripts, outputs and local Git evidence even without conversation history. Selected source files in a proposal are preserved in full locally; choose relevant excerpts when retaining an entire conversation is inappropriate.

The agent uses `saigen reconstruct propose --file proposal.json --revision REV` to publish evidence-linked draft cards. Inspect their details, source copies, classifications and unresolved gaps. Edit titles and notes in the normal editor.

Accept useful states independently of uncertain relationships. A relationship can be accepted once its endpoints are accepted. Rejecting a draft state also archives its pending relationships; accepted work stays intact. Review decisions retain the reviewer, time and any supplied reason. Use **Archive** to inspect rejected work.

The agent can record your decisions with `saigen reconstruct accept --id ID --state STATE --revision REV` or `--connection ACTION`. Omitting selectors reviews remaining draft items. Acceptance records a review decision, not proof that a historical command ran.

### Add later evidence or correct a proposal

For later evidence or overlapping work, ask the agent to create an explicit extension referencing existing accepted IDs. Additional citations are reviewed separately and appended alongside earlier evidence. They do not overwrite the original claims, and conflicting sources can remain visible. Use `--evidence ITEM_ID` to review a particular addition.

Correct unused draft structure through rejection and a revised proposal. Keep accepted history and record a supported decision when resolving conflicting interpretations. Repeated evidence graphs are detected even with renamed IDs or paths; intentional alternatives require an explicit relation and reason. Automatic semantic merging is not supported. See the [agent proposal reference](../skills/saigen-record/references/reconstruction.md) for the JSON format.

`saigen reconstruct show` lets another session resume the review; use `--id ID` to select one reconstruction. Each entry includes the current project revision, review status, original `spec`, and a `graph` with current titles, notes and connections. For rejected proposals, the graph comes from the archive. Agents should resume from `graph`, retaining `spec` as the original submission.

Acceptance records your review and keeps historical execution unobserved. Accepted states can be inputs to new recorded runs. Drafts cannot be used in wrapped runs or as workflow input bindings. Existing results can be exported with reconstruction labels and evidence references. Optional [verification](verification.md) records a separate attempt and comparison. Large-folder discovery and automatic chat-provider ingestion remain outside this scope. Git history can support code identity but cannot alone prove historical execution.
