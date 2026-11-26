"""Workspace-local shortcuts that share SaigenBio's recording guidance."""

_FORMATS = {
    "codex": (".agents/skills/{name}/SKILL.md", "name: {name}\n", "$"),
    "claude": (".claude/commands/{name}.md", "disable-model-invocation: true\n", "/"),
    "opencode": (".opencode/commands/{name}.md", "subagent: false\n", "/"),
}


def paths_for(name):
    return {agent: path.format(name=name) for agent, (path, _, _) in _FORMATS.items()}


RECONSTRUCTION_PATHS = paths_for("saigen-reconstruct")
ORGANIZATION_PATHS = paths_for("saigen-organize")
PIPELINE_PATHS = paths_for("saigen-pipeline")
WORKFLOW_DISCOVERY_PATHS = paths_for("saigen-find-workflow")
RECONSTRUCTION_INVOCATIONS = {
    agent: prefix + "saigen-reconstruct" for agent, (_, _, prefix) in _FORMATS.items()
}


def shortcut_files(agents, skill_folders):
    files = {}
    for agent in agents:
        if agent not in _FORMATS:
            continue
        skill = f"{skill_folders[agent]}/saigen-record/SKILL.md"
        path, metadata, _ = _FORMATS[agent]
        shortcuts = {
            "saigen-reconstruct": (
                "Reconstruct an existing analysis as an evidence-linked SaigenBio Canvas draft.",
                f"Read `{skill}` and follow its reconstruction guidance for the current workspace. "
                f"Use `saigen reconstruct sources --agent {agent}` with the configured CLI to identify "
                "candidate evidence. Confirm the source selection before reading transcripts and publish "
                "a draft for the researcher to review on the Canvas.",
            ),
            "saigen-pipeline": (
                "Select Canvas results and review a Nextflow or Snakemake export in this session.",
                f"Read the Export a pipeline from recorded results section of `{skill}`. "
                "Use any supplied state IDs as targets. If the targets are missing, ask the researcher to select "
                "results on the Canvas and use Copy node IDs, then paste the IDs here. "
                "Confirm the resolved targets and review the pipeline in chat.",
            ),
            "saigen-find-workflow": (
                "Recommend a published workflow for the researcher's goal and recorded inputs.",
                f"Read the Find a published workflow section of `{skill}`. "
                "Use any supplied Canvas state IDs and the researcher's goal to guide discovery.",
            ),
            "saigen-organize": (
                "Discuss and save analysis groups for the SaigenBio Canvas.",
                f"Read the Organize analysis groups section of `{skill}`. "
                "Ask how the researcher wants to organize the Canvas if they have not said. "
                "Propose a hierarchy of groups and existing states, refine the proposal with the researcher, "
                "and save it after agreement.",
            ),
        }
        for name, (description, prompt) in shortcuts.items():
            files[path.format(name=name)] = (
                f"---\n{metadata.format(name=name)}description: {description}\n---\n\n{prompt}\n"
            )
    return files
