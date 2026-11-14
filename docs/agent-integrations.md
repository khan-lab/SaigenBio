# Agent integrations

SaigenBio records through the same CLI for every agent. Agent setup supplies instructions; it does not enforce compliance or grant permissions.

## Prepare a workspace

After [installation](installation.md) and [project initialization](getting-started.md#open-an-analysis-directory), run setup from the directory you will open in your agent:

```sh
saigen setup --workspace . --agent claude --analysis-project . --viewer http://127.0.0.1:8767/
```

Replace claude with your chosen agent: codex, claude, opencode, or antigravity. Add --input PATH to identify available data; setup does not require a particular data directory. If the analysis project is a subdirectory of the agent workspace, set --analysis-project to that relative path. Setup creates a shared saigen-workspace.json and a copy of the same recording skill. Existing differing files cause a refusal before changes; merge those instructions deliberately or choose a fresh workspace. Project initialization and viewer startup remain separate. Input paths describe existing evidence; setup does not download data.

| Agent | Instructions | Skill directory | Verification |
| --- | --- | --- | --- |
| Codex | AGENTS.md | .agents/skills/saigen-record | Setup checked; recording exercised manually; full lifecycle acceptance pending |
| Claude Code | CLAUDE.md | .claude/skills/saigen-record | Documented convention; live acceptance pending |
| OpenCode | AGENTS.md | .opencode/skills/saigen-record | Documented convention; live acceptance pending |
| Antigravity | GEMINI.md | .agents/skills/saigen-record | Documented convention; live acceptance pending |

Sources: [Claude Code](https://claude.com/blog/steering-claude-code-skills-hooks-rules-subagents-and-more), [OpenCode skills](https://opencode.ai/docs/skills), [OpenCode rules](https://opencode.ai/docs/rules), [Antigravity skills](https://antigravity.google/docs/skills), [Antigravity customization](https://antigravity.google/docs/commands/learn), [Codex instructions](https://developers.openai.com/codex/guides/agents-md).

## Start a session

Open a fresh agent session in the workspace so it can load the project instructions. Describe your scientific task normally. The instructions point to the recording skill and the exact CLI path in saigen-workspace.json.

The selected Python environment must remain available at that path. When changing installations, review the configuration and workspace-local skill copy.

## Refresh existing workspace instructions

Setup copies the recording skill into the workspace. Upgrading SaigenBio does not update that copy, and rerunning setup refuses to overwrite differing files.

After upgrading the installation used by the workspace:

1. Read saigen-workspace.json to identify its CLI and agent. Use that CLI for the following setup command.
2. Generate the current instructions in a new temporary directory outside the software checkout: `saigen setup --workspace /absolute/path/to/new-temporary-directory --agent codex --analysis-project /absolute/path/to/existing-analysis`. Substitute your agent and paths. This generates instructions only; it does not initialize or execute analysis.
3. Compare the generated skill with the workspace copy at the agent-specific path in the table above. Back up the existing copy, then merge the updated guidance while retaining intentional local customizations. If there are no customizations, replace only the skill file with the generated one.
4. Retain the workspace's project, input, and viewer settings. If its CLI location changed, update the cli and python paths in saigen-workspace.json to the new installation. Review generated project instructions if needed rather than replacing existing instructions wholesale.
5. Open a fresh agent session so it loads the updated skill. Check a planning-only request before approving execution.

For concise planned nodes, the shared skill now separates short result titles, one-sentence expected results, proposed methods, and prerequisites. All supported agents receive this same guidance.

## Permissions and planning

Use the host's supported command approval for a blocked planning write. If unavailable, the user must change its permission settings. Codex CLI offers /permissions; this command is not a portable agent interface. For other agents use their current permission UI. Native planning modes may forbid writes regardless of filesystem permissions. No native read-only plan-mode integration is claimed.

Publishing a proposal and approving scientific execution are separate actions. Skill instructions cannot override host restrictions.

## Verification

See the [contributor acceptance procedure](agent-testing.md) for live-agent checks. Other agents can use the common configuration and skill through their own supported instruction mechanism.
