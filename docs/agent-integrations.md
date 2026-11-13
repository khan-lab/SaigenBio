# Agent integrations

SaigenBio records through the same CLI for every agent. Agent setup supplies instructions; it does not enforce compliance or grant permissions.

## Prepare a workspace

After installing the current package:

```sh
saigen setup --workspace /path/to/workspace --agent claude \
  --analysis-project projects/analysis --input data/input.tsv \
  --viewer http://127.0.0.1:8767/
```

Choose codex, claude, opencode, or antigravity. Setup creates a shared saigen-workspace.json and a copy of the same recording skill. Existing differing files cause a refusal before changes; merge those instructions deliberately or choose a fresh workspace. Project initialization and viewer startup remain separate. Input paths describe existing evidence; setup does not download data.

| Agent | Instructions | Skill directory | Verification |
| --- | --- | --- | --- |
| Codex | AGENTS.md | .agents/skills/saigen-record | Setup supported; user trials exercised recording, full lifecycle acceptance pending |
| Claude Code | CLAUDE.md | .claude/skills/saigen-record | Documented convention; live acceptance pending |
| OpenCode | AGENTS.md | .opencode/skills/saigen-record | Documented convention; live acceptance pending |
| Antigravity | GEMINI.md | .agents/skills/saigen-record | Documented convention; live acceptance pending |

Sources: [Claude Code](https://claude.com/blog/steering-claude-code-skills-hooks-rules-subagents-and-more), [OpenCode skills](https://opencode.ai/docs/skills), [OpenCode rules](https://opencode.ai/docs/rules), [Antigravity skills](https://antigravity.google/docs/skills), [Antigravity customization](https://antigravity.google/docs/commands/learn), [Codex instructions](https://developers.openai.com/codex/guides/agents-md).

## Permissions and planning

Use the host's supported command approval for a blocked planning write. If unavailable, the user must change its permission settings. Codex CLI offers /permissions; this command is not a portable agent interface. For other agents use their current permission UI. Native planning modes may forbid writes regardless of filesystem permissions. No native read-only plan-mode integration is claimed.

Publishing a proposal and approving scientific execution are separate actions. Skill instructions cannot override host restrictions.

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
