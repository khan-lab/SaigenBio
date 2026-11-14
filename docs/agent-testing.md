# Testing agent integrations

This procedure is for contributors validating a new agent or skill change. Setup generation alone does not establish reliable live recording.

## Initialization interview

In a temporary workspace outside the source checkout, run saigen init in a terminal. Try selecting several agents and flexible permissions, changing the port, declining viewer startup, and cancelling before creation. Check the generated instructions include the selected workflow preference and explicit permission for routine local SaigenBio UI implementation changes in flexible mode. No analysis should start. Check a busy port is not reused, the viewer starts on the saved port, and rerunning init preserves records and settings. Repeat with --non-interactive flags to check that scripts do not receive prompts. Host filesystem and network settings must remain unchanged.

For agent checkboxes, test Up/Down, Space to select/deselect, a to select all, n to clear, and Enter to confirm. Cancel midway and verify terminal input/echo recover. Check NO_COLOR disables prompt colors and a terminal without cursor support asks individual yes/no questions. When declining viewer startup, verify the displayed serve command includes the chosen port and correctly quotes a project path containing spaces.

## Fresh-session acceptance

Use the same sample/count fixture and scientific prompts in every agent:

1. Ask for a plot in sample-name order. Check recorded input, running state, final figure, and completion verification.
2. In a new project, ask for two proposed plots and require approval before execution. Check dotted nodes without edges, concise result titles, and one-sentence expected results without a repeated "Expected:" prefix. Include a requested method and review prerequisite: check they are preserved in details rather than embedded in the title or hover sentence. Confirm no analysis commands started.
3. Approve the plan. Check each state activates and completes individually and retains its original plan in details.
4. Request an alternative ordering. Check the original result remains preserved.
5. Exercise a failing command and retry. Verify failure history remains.
6. Block planning writes. Check scoped approval guidance and no accidental analysis execution.
7. Export selected results as PDF through the Report interface. Verify that exporting adds no report-only node or analysis edges and leaves the project revision unchanged. If new scientific calculations are needed for the report, check that they are recorded separately before export.

Record agent version, permission mode, project path, observed outcome, and failures. Installation checks do not establish fresh-agent compliance. Other agents can use the common configuration and skill through their own supported instruction mechanism.

Generate an isolated trial with scripts/check_installation.py --agent AGENT, then follow its workspace/START.md. Record results in the relevant issue or pull request. Personal transcripts and investigations belong in ignored docs/local/ or the external trial directory.
