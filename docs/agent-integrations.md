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

## Permissions and planning

Use the host's supported command approval for a blocked planning write. If unavailable, the user must change its permission settings. Codex CLI offers /permissions; this command is not a portable agent interface. For other agents use their current permission UI. Native planning modes may forbid writes regardless of filesystem permissions. No native read-only plan-mode integration is claimed.

Publishing a proposal and approving scientific execution are separate actions. Skill instructions cannot override host restrictions.

## Verification

See the [contributor acceptance procedure](agent-testing.md) for live-agent checks. Other agents can use the common configuration and skill through their own supported instruction mechanism.
