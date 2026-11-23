"""Agent-specific entry points for the shared reconstruction workflow."""

PATHS = {
    "codex": ".agents/skills/saigen-reconstruct/SKILL.md",
    "claude": ".claude/commands/saigen-reconstruct.md",
    "opencode": ".opencode/commands/saigen-reconstruct.md",
}

INVOCATIONS = {
    "codex": "$saigen-reconstruct",
    "claude": "/saigen-reconstruct",
    "opencode": "/saigen-reconstruct",
}

_DESCRIPTION = "Reconstruct an existing analysis as an evidence-linked SaigenBio Canvas draft."


def shortcut_files(agents, skill_folders):
    files = {}
    for agent in agents:
        if agent not in PATHS:
            continue
        skill = f"{skill_folders[agent]}/saigen-record/SKILL.md"
        extra = {
            "codex": "name: saigen-reconstruct\n",
            "claude": "disable-model-invocation: true\n",
            "opencode": "subagent: false\n",
        }[agent]
        files[PATHS[agent]] = (
            f"---\n{extra}description: {_DESCRIPTION}\n---\n\n"
            f"Read `{skill}` and follow its reconstruction guidance for the current workspace. "
            f"Use `saigen reconstruct sources --agent {agent}` with the configured CLI to identify "
            "candidate evidence. Confirm the source selection before reading transcripts and publish "
            "a draft for the researcher to review on the Canvas.\n"
        )
    return files
