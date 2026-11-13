# Testing agent integrations

This procedure is for contributors validating a new agent or skill change. Setup generation alone does not establish reliable live recording.

## Fresh-session acceptance

Use the same sample/count fixture and scientific prompts in every agent:

1. Ask for a plot in sample-name order. Check recorded input, running state, final figure, and completion verification.
2. In a new project, ask for two proposed plots and require approval before execution. Check dotted nodes without edges.
3. Approve the plan. Check each state activates and completes individually.
4. Request an alternative ordering. Check the original result remains preserved.
5. Exercise a failing command and retry. Verify failure history remains.
6. Block planning writes. Check scoped approval guidance and no accidental analysis execution.
7. Export selected results as PDF.

Record agent version, permission mode, project path, observed outcome, and failures. Installation checks do not establish fresh-agent compliance. Other agents can use the common configuration and skill through their own supported instruction mechanism.

Generate an isolated trial with scripts/check_installation.py --agent AGENT, then follow its workspace/START.md. Record results in the relevant issue or pull request. Personal transcripts and investigations belong in ignored docs/local/ or the external trial directory.
