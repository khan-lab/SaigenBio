# Contributing to SaigenBio

Contributions should help researchers understand analysis choices and inspect the evidence behind results. Use [Issues](https://github.com/khan-lab/SaigenBio/issues) for reproducible bugs and concrete proposals. For a substantial feature, discussing its scope first can avoid duplicated work.

## Development setup

Requirements: Python 3.10+ and Node.js for browser-code checks. The isolated installation-check script additionally uses uv. Optional PDF integration checks require Quarto with its bundled Typst engine. Shell-session recording requires zsh on POSIX.

Obtain the source as described in [Installation](docs/installation.md#obtain-the-source). For development, install it in editable mode in your preferred environment. With Python's virtual environment:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --editable .
```

The backend has no third-party Python runtime dependencies. Run source commands with python3 -m saigen when checking the checkout directly. Keep generated projects outside this repository.

## Repository map

| Path | Purpose |
| --- | --- |
| saigen/ | CLI, records, execution, local server, shell sessions, reports |
| ui/ | Plain HTML, CSS, and JavaScript viewer |
| skills/ | Shared agent recording instructions |
| tests/ | Recorder, HTTP, session, report, and display checks |
| scripts/check_installation.py | Isolated wheel-installation check |
| examples/ecoli/ | Optional example helpers |
| docs/ | Maintained user and contributor documentation |

Read [responsibility ownership](docs/architecture.md#responsibility-ownership) before adding behavior. Identify which component owns it and keep shared record validation in the recorder. PRs that change configuration or stored records should explain compatibility with existing workspaces. Keep scientific workspaces, installed applications, and development checkouts distinct.

Use the component names **Saigen Engine**, **Saigen Skills**, and **Saigen Canvas**. Consult the [module map and dependency direction](docs/architecture.md#module-map-and-dependency-direction) when choosing where code belongs. Shared record rules live in `saigen/records.py`; persistence and services enforce them for both CLI and HTTP callers. Derived Canvas responses belong in `saigen/views.py`, while browser presentation belongs in `ui/`. Codex and Claude Code remain external agents guided by Skills. Keep one installation and preserve existing record formats and entry points during focused refactors.

For workflow extensions, read the [adapter contract](docs/workflow-adapters.md) and [current integration status](docs/workflows.md). Keep adapters independent of recorder writes and distinguish declared plans from observed engine evidence.

## Checks

From the checkout:

```sh
python3 -B -m unittest discover -s tests -v
node --check ui/app.js
node tests/test_path_display.cjs
node tests/test_action_junctions.cjs
node tests/test_node_geometry.cjs
node tests/test_reports_ui.cjs
node tests/test_workflows_ui.cjs
node tests/test_story_ui.cjs
node tests/test_detail_controller.cjs
node tests/test_reconstruction_ui.cjs
node tests/test_plan_removal_ui.cjs
git diff --check
```

Run the checks relevant to your change. Browser interaction changes also need a live viewer check: selection, dragging, delayed previews, detail navigation, and returning from report selection.

For packaging or agent-setup changes:

```sh
python3 -B scripts/check_installation.py --agent codex
```

Add --with-quarto to verify PDF/source-bundle downloads. Change --agent to claude, opencode, or antigravity to exercise another setup layout.

The checker creates an external directory under ../SaigenBio-lab/installations/ by default; --destination /outside/path/new-trial selects another new location. Build sources, wheel, environment, logs, cache, and trial outputs stay there. Existing destinations are rejected. Inspect installation-check.json and workspace/START.md.

A successful package check does not prove an AI agent will follow the skill. Use the [agent acceptance procedure](docs/agent-testing.md) for that.

For reconstruction changes, run the [installed mixed-source journey](docs/agent-testing.md#installed-reconstruction-journey). It exercises selective review, later evidence, explicit verification outcomes and frozen reports using synthetic data outside the source checkout. Keep live-agent acceptance evidence separate from deterministic integration results.

Real Nextflow checks are opt-in: see [local workflow integration](docs/nextflow.md#reproduce-the-real-test). Supply a new external destination under SaigenBio-lab and keep downloaded data, pipeline work directories and engine installs there.

## Preparing a pull request

Explain the user-visible problem, resulting behavior, and relevant verification. Update documentation when commands or interactions change. Preserve existing analysis history and keep inferred provenance distinct from observed execution.

Do not commit downloaded data, local environments, analysis databases, model outputs, or credentials. Use small synthetic fixtures for automated tests. New schema or execution behavior should have tests covering meaningful invariants and failures.

## Documentation and local notes

Tracked documentation must work for a reader without access to a maintainer's computer or prior conversations. Keep stable behavior in user guides and architecture documentation. Track agreed future work in Issues.

The ignored docs/local/ directory is available for personal memoranda, draft plans, rehearsal notes, and investigations. It is not distributed to contributors and must not be required by tracked documentation, code, or skills. Promote useful conclusions into shared documentation or Issues deliberately.

## Optional biological examples

The public tutorial downloads processed teaching data and needs no existing private project. The helpers under examples/ecoli/ also support a pre-existing ecoli-evol layout; they are optional development examples, not installation prerequisites:

```sh
python3 examples/ecoli/ecoli_example.py --source /path/to/ecoli-evol --project /path/to/new-analysis
```

Consult each helper's --help and inspect its expected inputs before use.

## Workflow comprehension review

Review planned, completed, failed and repeated runs. Looking at each stage on its own, a reader must be able to identify the operation, tool, workflow engine, important settings and status. Confirm the relationship remains understandable without the shared workflow heading. Inspect a cropped card and the hover/detail view on desktop and narrow screens. Verify that declared method descriptions, verified engine identity and missing information remain distinguishable. Label existence and a screenshot without JavaScript errors do not alone establish comprehension.
