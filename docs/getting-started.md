# Getting started

## Open an analysis directory

[Install SaigenBio](installation.md), then choose the directory where you want to keep your analysis. It can contain existing data and scripts or be a new directory. It does not need a prescribed folder layout.

From that directory:

```sh
saigen init --project . --name "My analysis"
saigen serve --project . --port 8767
```

Open http://127.0.0.1:8767/ and leave the viewer running. SaigenBio stores its records under .saigen/ in this directory. Initialization does not automatically import files or reconstruct earlier executions.

You can also use --project /path/to/analysis from another directory. Keep scientific projects separate from the SaigenBio software checkout.

## Record your work

Choose the workflow that fits your analysis:

- **AI agent:** follow [Agent integrations](agent-integrations.md) once, then describe your scientific task in the agent's chat.
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
saigen serve --project . --port 8767
```

The graph is stored on disk. Tell a new agent to inspect the existing flow before continuing. If the port is occupied, stop the old viewer or choose a free port and update the workspace configuration.

Keep the complete project directory, including .saigen/. See [backup and export](recording.md#inspect-and-export) and [PDF reports](reports.md).
