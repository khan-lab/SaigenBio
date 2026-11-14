# Recording reference

Install SaigenBio using [Getting started](getting-started.md). Use saigen SUBCOMMAND --help for complete options. --project works before or after the subcommand.

## Record a human shell session

The installation provides `saigen`; `python3 -m saigen` remains supported. `--project` works before or after the subcommand.

Start the viewer in one terminal:

```sh
saigen init --project ../SaigenBio-lab/projects/demo --name "Live demo" --non-interactive
saigen serve --project ../SaigenBio-lab/projects/demo
```

Open the printed viewer address (normally http://127.0.0.1:8767/). In another terminal:

```sh
saigen start --project ../SaigenBio-lab/projects/demo
```

For an existing graph, select a starting state with `--from "Unfiltered variants"`. A title must be unique; a state ID also works. An uninitialized project is created automatically. The session keeps your current directory and runs normal commands there. It loads your zsh configuration and installs temporary hooks in the new shell without editing your configuration files.

Run an analysis, then save its meaningful result:

```sh
python analysis.py
saigen save --title "Depth 5 results" \
  --output results/depth5.vcf \
  --output results/counts.svg \
  --script analysis.py \
  --reason "Check sensitivity to the depth threshold"
```

The example assumes your analysis produces those files. Run `save`, `pause`, and `resume` as separate shell submissions after the preceding foreground command returns.

- Commands, working directories, timestamps, shell exit status, and pipeline statuses are recorded automatically. Commands alone add no canvas nodes.
- `save` preserves selected files and creates a **Saved** state. Its details contain the commands since the previous save, including failures and recording gaps. The grouping is declared by the saver; it does not establish file dependencies or which command produced a file.
- Save output and script paths are relative to your current shell directory. Each save preserves separate file versions. Git context and explicit scripts are captured at save time, not automatically at each command.
- The first save in an empty project is a root state; later saves continue from the previous state. `save --from "State title"` branches elsewhere; it selects a record and does not restore that state into your working directory.
- `saigen commands` shows pending commands; `saigen status` shows session status. `saigen pause` and `saigen resume` control recording. `exit` ends the session.
- Only top-level interactive zsh submissions are observed. A pipeline is one submission, with shell-reported pipeline statuses. Child scripts, nested shells, notebooks, and agent tools are not expanded into separate records. Background launch status is not job completion. Interrupted commands remain unknown.
- The default captures neither raw keystrokes nor terminal output. Session shell-history writes are disabled to avoid a second unredacted copy. Basic secret detection omits suspicious commands before storage; it is not a complete secret detector. Pause for private work.
- `start --record-output` opts in to an unredacted output transcript, which can include echoed commands and sensitive output. Pause suppresses transcript writes too. The transcript is preserved as a session log on exit.

`saigen run` still records explicit execution and declared inputs/outputs. Inside a recorded shell it links to the session without a duplicate shell step; a successful run becomes the next starting state. An AI writer should specify `--actor "AI agent"`. Launching an agent in a recorded shell does not capture its internal tools: its recording skill must continue to use `run`.

The viewer updates automatically when you save. A terminal checkpoint has no running analysis arrow before saving because its grouping and outputs have not yet been declared.

## Record existing evidence

```sh
python3 -m saigen --project /path/to/analysis snapshot \
  --id input --title "Starting data" \
  --file data/input.tsv \
  --note "Existing evidence; upstream execution has not been recorded."
```

The input file is copied into the project's artifact store. Use --reference instead of --file for a large file that should remain an external reference.

## Record a new run

```sh
python3 -m saigen --project /path/to/analysis run \
  --from input --title "Summary" --label "summarize.py" \
  --reason "Inspect the distribution before choosing the next analysis." \
  --input data/input.tsv --output summary.svg \
  --script scripts/summarize.py \
  -- python3 "{project}/scripts/summarize.py" "{input:0}" summary.svg
```

The example assumes your project contains that script and input file. The command runs in a fresh directory under .saigen/runs. Output paths are relative to that directory. The recorder supplies these substitutions in individual command arguments:

| Placeholder | Meaning |
| --- | --- |
| {project} | Analysis project directory |
| {run} | This attempt's working directory |
| {input:0} | Preserved copy of the first declared input |

Use --input artifact:ARTIFACT_ID to reuse an existing recorded file. Repeat --from for a comparison with multiple parent states. Use --stdout result.txt for a tool that writes its result to standard output. Supply an explicit shell command only when a shell is needed.

The recorder observes exit status and checks declared outputs. A scientific claim still requires interpretation and validation. Imports, plans, actor labels, and stated reasons are distinguished from observed process facts.

Declare scripts with --script and lock files with --environment. --source-repo identifies the code repository when it differs from the analysis project. --tool-version records a supplied version statement; it is not an automatic probe.

## Inspect and export

```sh
python3 -m saigen --project /path/to/analysis flow
python3 -m saigen --project /path/to/analysis history
python3 -m saigen --project /path/to/analysis export project-history.json
```

The export contains records, not the file bodies. Back up the complete .saigen directory to preserve the project, including its artifacts. The recorder uses SQLite transactions; copy a live database using SQLite backup facilities or stop writers before copying the directory.

## Planned output states

Agents can publish future results without execution edges:

```sh
saigen plan --project /path/to/analysis --from input --id summary_plan \
  --title "Sample count summary" \
  --expect "A plot showing the number of samples in each group." \
  --details "Count samples using the recorded group metadata." \
  --requires "Confirm group labels before counting." --output counts.svg
```

Use another planned ID as --from to propose later steps. After user approval, execute into the same placeholder using the normal run options plus --plan summary_plan --approved. Its actual parents must match the proposal and already contain completed or imported evidence. The node retains its position; the incoming edge appears when execution starts. The approval flag is an agent declaration, not an approval interface.

Use a short result name for --title (usually 3–6 words) and one expected-result sentence for --expect, without an "Expected:" prefix. The canvas shows the title and status; hover shows the expected result. Optional --details describes the proposed method and --requires describes a prerequisite. Both appear in the detail view, alongside planned inputs and expected files. Prerequisites are explanatory text; SaigenBio does not enforce them or infer approval from them. The original plan remains in the state details after execution starts. Older records remain readable with their original text.

For immediate execution, run --expect describes the expected output on the running placeholder. Completion replaces the placeholder with preserved results. Failed attempts remain recorded.


## Acquire data and annotate results

acquire uses run's execution options without --from. It records a root acquisition with no incoming edge. Declare public sources through --source-url and downloaded files through --output. The download command must actually run inside the wrapper; importing a file later does not establish its download history.

```sh
saigen acquire --project /path/to/analysis --title "Public dataset" --expect "A downloaded CSV dataset." --source-url https://example.org/data.csv --output data.csv -- curl --fail --location https://example.org/data.csv --output data.csv
```

This illustrates the command shape; replace the example URL with a real source.

Add or revise a scientific summary without changing execution facts:

```sh
saigen annotate --project /path/to/analysis --state STATE_ID --note "Dataset summary and known limitations."
```

For everyday agent use, describe the scientific task. The [recording skill](../skills/saigen-record/SKILL.md) supplies these mechanics.
