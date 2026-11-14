# Getting started

## Open an analysis directory

[Install SaigenBio](installation.md), then choose the directory where you want to keep your analysis. It can contain existing data and scripts or be a new directory. It does not need a prescribed folder layout.

From that directory:

```sh
saigen init
```

In a terminal, init asks for a project name, one or more AI agents (or none), agent workflow permissions, a viewer port, and whether to start the viewer. Review the settings before creating the workspace. Supplied flags skip their questions. Cancelling the interview leaves files unchanged.

The default name is the folder name. The interview suggests an available port starting at 8767. Open the printed viewer address and leave the terminal running; Ctrl+C stops the viewer. If you choose to start it later, run `saigen serve` from the analysis directory. It reuses the saved port.

SaigenBio stores records under .saigen/, viewer settings in .saigen/viewer.json, and agent setup in saigen-workspace.json plus the selected agents' instruction and skill files. Initialization does not import data or run analysis. Existing conflicting instruction files are reported before a project is created.

For scripts or agents, use flags without an interview:

```sh
saigen init --project /path/to/analysis --name "My analysis" \
  --agent codex --agent claude --permissions flexible \
  --port 8767 --non-interactive
```

Non-interactive init does not start a viewer unless --start-viewer is supplied. Without a terminal it automatically uses this non-interactive behavior. Omit --agent to skip agent setup. An explicitly chosen busy port produces an error; no existing service is stopped. See [workflow permissions](agent-integrations.md#workflow-permissions) for what flexible mode authorizes.

You can also use --project /path/to/analysis from another directory. Keep scientific projects separate from the SaigenBio software checkout.

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

Edits save to the project. Notes and layout can change; recorded execution facts are retained. Undo checks for conflicting changes.

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
