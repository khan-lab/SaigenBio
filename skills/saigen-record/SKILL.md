---
name: saigen-record
description: Record an AI agent's biological analysis actions in a local SaigenBio project, preserving parent states, commands, outputs, and stated reasons. Use for analyses the user wants represented in a SaigenBio flow.
---

# Record an analysis

Use the installed `saigen` CLI from the user's analysis workspace. Check `saigen --version` and use `saigen SUBCOMMAND --help` for available options. The source repository is not required. Select the analysis project explicitly with `--project PATH`; keep generated data and trials in that workspace, not in the installed skill folder.

Initialize with `saigen init --project PATH --name NAME`. View it with `saigen serve --project PATH --port PORT`, choosing a free port without stopping an unrelated viewer. If the CLI is missing, report the missing dependency instead of assuming a source checkout is available.

For a recorded action, the command shape is:

```sh
saigen run --project PATH --actor "AI agent" \
  --from STATE --title TITLE --label LABEL --reason REASON \
  --input artifact:ID --output figure.svg --script scripts/plot.py \
  -- python3 "{project}/scripts/plot.py" "{input:0}" figure.svg
```

Adapt the script, arguments, and outputs to the authorized task. `--script` and ordinary input paths resolve against the analysis project; output paths resolve against the isolated run directory. Use `saigen flow --project PATH` to obtain actual state and artifact IDs. `snapshot --file PATH` imports files into a starting state.

The recorder supports authorized analysis work; using this skill does not authorize additional experiments, uploads, or changes to unrelated projects.

- Inspect `flow` before choosing parent states. Use preserved inputs from imported or completed states. A Git commit is a code reference, not a state ID.
- Import existing evidence with `snapshot`. Explain which upstream execution details are unknown. Do not reconstruct an observed command from a current script alone.
- Use `run` for a new action. Declare the parent state, a short title and arrow label, the reason, input files, and expected outputs. Record an unknown reason as unknown rather than inventing a rationale.
- Use `--input artifact:ID` for preserved prior files and `{input:0}` in command arguments to read the recorded copy. Commands run in their own fresh working directory.
- Declare relevant scripts and environment files with `--script` and `--environment`. Set `--source-repo` when code lives elsewhere. Supplied tool versions and actor names are declarations.
- Let the wrapper determine execution status. Do not claim success from a planned edge, an animation, a current file name, or exit code zero alone. Inspect the recorded files and logs before interpreting results.
- Keep a failed attempt. A retry is a new run from an appropriate preserved parent, with its changed command or rationale made explicit.
- Repeat `--from` for a comparison that depends on more than one state.
- Do not write the SQLite database or edit recorded execution facts directly. The recorder owns process facts; the viewer adds annotations and manual plans.

The recorder captures declared files and the launched command. It does not automatically capture every tool call, conversation, or dependency.

## Recorded human sessions

`saigen start --project PATH --from "Unique state title"` opens an interactive zsh with command capture. Omit --from in an empty project. Only top-level submissions are observed; launching an agent inside it does not capture the agent’s internal tools.

- Continue using `saigen run --actor "AI agent"` for agent analysis actions. Runs in a recorded session link without duplicate shell nodes. Do not start an interactive session from an unattended agent tool invocation.
- A human can run ordinary commands and use `saigen save --title TITLE --output FILE --reason REASON` to preserve meaningful results. Each save groups pending activity. It is a captured checkpoint, not verified successful execution or proof of file dependencies.
- Save paths are relative to the current shell directory. Declare scripts with --script; scripts and Git context are captured at save time.
- Use pause/resume as separate shell submissions for private activity. Command redaction is limited; optional output transcripts are unredacted.
- A successful wrapped run becomes the next starting state. Use --from to branch elsewhere; this selects a record, not a filesystem checkout.
