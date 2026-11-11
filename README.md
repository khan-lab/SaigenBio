# SaigenBio

A local analysis recorder and a plain HTML flow viewer. States contain preserved files. Arrows show recorded commands or explicit plans. The original illustrative version remains in [saigenbio_mock.html](saigenbio_mock.html).

Read the [implementation plan](docs/implementation-plan.md) for the product decisions and delivery order.

## Start a project

Use Python 3.10 or newer. The recorder and viewer use the Python standard library.

Run these commands from this repository:

```sh
python3 -m saigen --project /path/to/analysis init --name "My analysis"
python3 -m saigen --project /path/to/analysis serve
```

Open http://127.0.0.1:8765. The service reads and writes that project's .saigen directory. The browser does not execute commands.

## Prepare a demo workspace

From this repository, run:

```sh
bash setup.bash
```

The default location is the visible directory demos/advisor-demo. Pass another directory as the first argument for a new rehearsal. The script requires Pixi and SaigenBio on PATH, installs the analysis tools, creates the folders, and initializes the project. Existing environments use their lock file. Data downloads and analysis are performed afterward by the agent.

Start the viewer separately:

```sh
saigen serve --project demos/advisor-demo
```

The entire demos directory is Git-ignored, including its input data, outputs, environments, and recorded analysis history.

## Record a human shell session

Install the CLI from this repository:

```sh
uv tool install --editable .
```

The installation provides `saigen`; `python3 -m saigen` remains supported. `--project` works before or after the subcommand.

Start the viewer in one terminal:

```sh
saigen init --project .saigen-projects/demo --name "Live demo"
saigen serve --project .saigen-projects/demo
```

Open http://127.0.0.1:8765. In another terminal:

```sh
saigen start --project .saigen-projects/demo
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

## Agent integration

The repository and installed package include [the recording skill](skills/saigen-record/SKILL.md). The skill uses the installed CLI and is self-contained. A wheel installs it under `share/saigenbio/skills/saigen-record` in its Python environment. Copy that whole folder into your analysis workspace's `.agents/skills/` for a local Codex installation; global agent configuration is not changed automatically. See the external installation check below for a tested setup.

Hover over an arrow for action details, or over its label for a compact list of related scripts, inputs, and outputs. File entries show project-relative paths or aliases for external locations, offer Copy displayed path, and open preserved previews. Commands use the same display paths; the executable is shown by name. In state details, expand Code, inputs, and environment to reveal the Exact local command control.

Display aliases such as {source}, {scripts}, and {external:1} hide parent directories; they are not shell variables. Original local records, exports, and file contents retain their full paths.

Human notes, layout edits, new plans, and Undo are saved through the viewer. Actual execution facts remain attached to their original attempts.

## Test a clean installation outside the repository

Keep reusable test code here; put installation environments, trial projects, build files, and screenshots in a separate workspace. From this checkout:

```sh
python3 -B scripts/check_installation.py
```

The check creates a new visible `../SaigenBio-lab/installations/install-TIMESTAMP/` directory. It copies the package sources there, builds a wheel, installs it into a fresh environment (not editable), installs the bundled skill into the trial's `workspace/.agents/skills/`, and verifies a recorded action plus the installed viewer and plot endpoint. The existing CLI installation and viewers are untouched.

All generated files, including the build cache and logs, stay in that trial directory. The report is `installation-check.json`; `workspace/START.md` explains how to open a fresh agent session and test skill discovery. Automatic skill selection still needs that fresh-session check.

An optional `--destination /outside/path/new-trial` selects another new directory. Existing destinations and paths inside this checkout are rejected.

To also test Quarto rendering and PDF/source-bundle downloads from the installed package:

```sh
python3 -B scripts/check_installation.py --with-quarto
```

This requires `quarto` on PATH. Generated reports and downloaded copies stay in the external trial directory.

For biological demonstrations, select an external directory explicitly:

```sh
bash setup.bash ../SaigenBio-lab/projects/advisor-demo
saigen serve --project ../SaigenBio-lab/projects/advisor-demo
```

Existing `.saigen-projects/ecoli` contains preserved analysis history, including depth 5. Keep each project's complete `.saigen` directory together; deleting individual run or object files can break its record. Git ignore rules prevent commits but do not remove files from disk.

## Real example and checks

```sh
python3 scripts/ecoli_example.py --source /path/to/ecoli-evol
python3 -m saigen --project .saigen-projects/ecoli serve
python3 -m unittest discover -s tests -v
node tests/test_path_display.cjs
```

The example imports existing variant calls, then records fresh filtering, summaries, figures, and a comparison. It uses the source repository's installed bcftools and vcfutils.pl and does not modify its analysis outputs. Repeating the example adds new attempts.

The local service is intended for one machine. Notebook adapters, accounts, remote execution, large-file streaming, and portable import/replay are later work.

## Create a selected-state PDF report

Install Quarto with its bundled Typst engine and keep `quarto` on PATH. In the viewer, choose **Report**, then click states in the order you want to present them. Numbered badges show that order. Clicking a selected state removes it; selecting it again appends it. **Clear** resets the selection, **Cancel** leaves report mode, and **Create PDF** starts a local render with visible status. Download the PDF or its source bundle when ready. Report selection is separate from graph editing.

Reports include only the selected states, their saved figures, recorded notes, incoming action reasons and commands, and compact source references. Named omitted parents provide context; presentation order does not assert execution order or dependencies. No analysis runs, recorded commands execute, or biological interpretations are generated. Current statuses, missing evidence and unsupported figures are stated explicitly.

Each report is saved under `.saigen/reports/REPORT_ID/` with `report.pdf`, editable `report.qmd`, a controlled `_quarto.yml`, included figure files, `snapshot.json` and `manifest.json`. The ZIP includes those files. The manifest fixes the selected IDs/order and project revision, and hashes the selected snapshot, source and copied figures plus the resulting PDF. Graph edits after export do not change the saved report. From the extracted bundle, run:

```sh
quarto render report.qmd --to typst --output report.pdf --no-execute
```

The report aliases local paths. Labels embedded inside original figure files are preserved unchanged and can still contain paths or sensitive text. The selected snapshot is a record excerpt, not a full database backup or an analysis replay package; nonfigure source files are referenced by name and hash rather than bundled. The manifest pins source evidence, not a byte-identical PDF across Quarto/font versions.

The first version supports preserved SVG, PNG and JPEG figures, up to 20 MB per figure, 100 MB total, and 50 selected states. SVGs containing embedded/linked content or external declarations are omitted with a warning. External references are never read by reporting. Recorded Markdown is escaped as display text; executable blocks and includes are not interpreted. Rendering uses a fixed Quarto argument list, disabled code execution and a controlled project configuration. One report renders at a time, with a three-minute timeout. Downloads require the viewer session token; download links last for the server session, while saved report files remain on disk. A renderer error leaves its local `render.log` for inspection.
