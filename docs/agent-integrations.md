# Agent integrations

SaigenBio records through the same CLI for every agent. Agent setup supplies instructions; it does not enforce compliance or grant permissions.

## Prepare a workspace

The [init interview](getting-started.md#open-an-analysis-directory) can set up one or more agents as it creates the project. For an existing project, a separate agent workspace, or an additional agent, run setup from the directory you will open in your agent:

```sh
saigen setup --workspace . --agent claude --analysis-project .
```

Replace claude with codex, claude, opencode, or antigravity. Repeat --agent to select several. Add --input PATH to identify available data; setup does not require a particular data directory. If the analysis project is a subdirectory of the agent workspace, set --analysis-project to that relative path. Setup creates a shared saigen-workspace.json and copies the same recording skill for the selected agents. It can add agents to an existing generated setup while preserving the viewer, workflow preference, and configuration paths. Shared instruction files include the relevant skill locations for both agents.

Customized or conflicting instructions cause a refusal before any files are changed; merge them deliberately or choose a fresh workspace. Keep the same --analysis-project and --input values when extending an existing setup. For a new standalone setup, --viewer sets its URL (default http://127.0.0.1:8767/). Existing setups retain their viewer URL unless explicitly changed in configuration. Standalone setup does not initialize the project or start the viewer. Input paths describe existing evidence; setup does not download data.

| Agent | Instructions | Skill directory | Verification |
| --- | --- | --- | --- |
| Codex | AGENTS.md | .agents/skills/saigen-record | Setup checked; recording exercised manually; full lifecycle acceptance pending |
| Claude Code | CLAUDE.md | .claude/skills/saigen-record | Documented convention; live acceptance pending |
| OpenCode | AGENTS.md | .opencode/skills/saigen-record | Documented convention; live acceptance pending |
| Antigravity | GEMINI.md | .agents/skills/saigen-record | Documented convention; live acceptance pending |

Sources: [Claude Code](https://claude.com/blog/steering-claude-code-skills-hooks-rules-subagents-and-more), [OpenCode skills](https://opencode.ai/docs/skills), [OpenCode rules](https://opencode.ai/docs/rules), [Antigravity skills](https://antigravity.google/docs/skills), [Antigravity customization](https://antigravity.google/docs/commands/learn), [Codex instructions](https://developers.openai.com/codex/guides/agents-md).

## Start a session

Open a fresh agent session in the workspace so it can load the project instructions. Describe your scientific task normally. The instructions point to the recording skill and the exact CLI path in saigen-workspace.json.

The selected Python environment must remain available at that path. When changing installations, review the configuration and workspace-local skill copy. For a first project, follow the [complete first-run walkthrough](getting-started.md#open-a-fresh-agent-session) rather than copying instructions from an older workspace. An independent restart should use a [new empty directory](getting-started.md#restart-with-a-fresh-analysis).

## Refresh existing workspace instructions

Setup copies the recording skill into the workspace. Upgrading SaigenBio does not update that copy, and rerunning setup refuses to overwrite differing files.

After upgrading the installation used by the workspace:

1. Read saigen-workspace.json to identify its CLI and agent. Use that CLI for the following setup command.
2. Generate the current instructions in a new temporary directory outside the software checkout: `saigen setup --workspace /absolute/path/to/new-temporary-directory --agent codex --analysis-project /absolute/path/to/existing-analysis`. Substitute your agent and paths; repeat --agent for multiple agents. If the existing project uses a saved permissionMode, also supply its matching --permissions ask or --permissions flexible option so generated instructions retain that authorization. This generates instructions only; it does not initialize or execute analysis.
3. Compare the generated skill and project instructions with the workspace copies at the agent-specific paths in the table above. Back up existing files, then merge updated guidance while retaining intentional local customizations. If the skill has no customizations, replace that skill file with the generated one. Review project instructions separately; do not replace them wholesale or change the chosen workflow permission accidentally.
4. Retain the workspace's project, input, and viewer settings. If its CLI location changed, update the cli and python paths in saigen-workspace.json to the new installation. Review generated project instructions if needed rather than replacing existing instructions wholesale.
5. Open a fresh agent session so it loads the updated skill. Check a planning-only request before approving execution.

For concise planned nodes, the shared skill now separates short result titles, one-sentence expected results, proposed methods, and prerequisites. All supported agents receive this same guidance.

## Permissions and planning

### Workflow permissions

The init interview asks independently about analysis permissions and SaigenBio UI development. Both choices are saved in saigen-workspace.json and described in agent instructions. Analysis uses permissionMode:

| Choice | Authorized behavior |
| --- | --- |
| ask | Requested workspace edits may proceed; ask before proposed downloads and analysis runs. |
| flexible | Proceed with requested edits, public-data downloads, and analysis runs without asking for each step. |

UI source changes use `uiDevelopment`: `ask` (default) requires approval; `allow` authorizes routine local UI fixes and improvements. Use `--ui-development ask` or `--ui-development allow` with init or setup. This choice concerns SaigenBio application source, while canvas plans, notes, and layout remain workspace edits. Locate the source checkout before editing application code.

Older configurations without `uiDevelopment` retain their original meaning: Flexible also grants the routine local UI development permission previously selected. Setup preserves this legacy behavior rather than silently changing authorization. To change permissions in an existing workspace, deliberately update its configuration and corresponding agent instructions together; customized files are never overwritten automatically.

Use --permissions ask or --permissions flexible with init, or when creating a new standalone setup. In both modes, planning-only requests and explicit review checkpoints still mean wait. Destructive changes, uploads, spending money, and work outside the authorized scope still require approval. Existing workflow preferences are retained when adding agents; changing a preference requires deliberately updating both the configuration and instructions.

These are agent instructions, not operating-system or host permissions. They do not change global agent configuration, grant filesystem or network access, or guarantee that a host will stop asking. To permit the chosen workflow, allow writes to the analysis workspace and, if UI source edits are desired, the SaigenBio source checkout; enable the needed network access in the agent host. See the official [OpenAI agent approvals and security guidance](https://learn.chatgpt.com/docs/agent-approvals-security) for Codex. Other agents have their own permission controls.

### Host restrictions

Use the host's supported command approval for a blocked planning write. If unavailable, the user must change its permission settings. Codex CLI offers /permissions; this command is not a portable agent interface. For other agents use their current permission UI. Native planning modes may forbid writes regardless of filesystem permissions. No native read-only plan-mode integration is claimed.

Publishing a proposal and approving scientific execution are separate actions. Skill instructions cannot override host restrictions.

## Verification

See the [contributor acceptance procedure](agent-testing.md) for live-agent checks. Other agents can use the common configuration and skill through their own supported instruction mechanism.
