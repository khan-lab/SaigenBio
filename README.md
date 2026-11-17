<img src="ui/assets/logo.svg" width="80" height="80" alt="SaigenBio logo">

# SaigenBio

**A visual analysis recorder for bioinformaticians working with AI agents.**

Biological analysis increasingly develops through conversation: a researcher asks a question, discusses a plan with an AI agent, inspects the results, and decides what to try next. New questions lead to different parameters, alternative methods, and returns to earlier steps. As agents accelerate this trial and error, the analysis can grow into a complex flow of branches and revisions.

SaigenBio helps manage that exploration for reproducibility. It connects recorded commands, scripts, inputs, outputs, and stated decisions in a visual flow, so researchers can trace how a result was produced and understand what changed between attempts.

Use your preferred AI agent to explore the biology. Use SaigenBio to keep the evolving analysis understandable, inspectable, and ready to share. States contain preserved results; arrows show the actions that produced them.

## What SaigenBio consists of

SaigenBio is a local tool that helps bioinformaticians and AI agents keep track of biological analyses. Its core is an analysis recording system, accessed through a command-line interface (CLI) and displayed as a visual workflow.

| Component | Role |
| --- | --- |
| Agent skills | Instructions explaining how AI agents should plan analyses and record commands, inputs, outputs, and decisions |
| CLI | Commands for recording data, publishing plans, running analyses, and exporting results |
| Recording system | Stores analysis states, execution records, preserved files, and the relationships between them |
| Visual UI | Lets researchers review plans and results, inspect their provenance, and edit the canvas |

The researcher and agent decide what to investigate. Scripts, analysis tools, and workflow engines perform the computation; SaigenBio records and visualizes the work. On the canvas, nodes represent analysis states or results, and arrows represent the actions connecting them.

For implementation responsibilities and storage details, see [Architecture](docs/architecture.md).

## What you can do

- Follow analysis as it runs, from a planned output to a completed result.
- Compare branches with different parameters while preserving earlier outputs.
- Inspect figures, table excerpts, commands, inputs, and recorded reasons.
- Record AI-driven analysis or meaningful checkpoints from a human shell session.
- Export selected states and figures through Quarto.

## Start here

SaigenBio requires Python 3.10+. Use your preferred Python environment or application installer.

1. [Install SaigenBio](docs/installation.md).
2. [Open an analysis project](docs/getting-started.md).
3. Optionally [connect your AI agent](docs/agent-integrations.md).

Already have an analysis? [Bring in existing work and saved conversations](docs/getting-started.md#bring-in-an-existing-analysis), including local Codex session files, for an agent-assisted reconstruction and review.

For a guided scientific example, follow the [E. coli tutorial](docs/tutorials/ecoli-exploration.md).

## Documentation

| Goal | Guide |
| --- | --- |
| Choose an installation method | [Installation](docs/installation.md) |
| Set up a project and use the canvas | [Getting started](docs/getting-started.md) |
| Explore real data and compare thresholds | [E. coli tutorial](docs/tutorials/ecoli-exploration.md) |
| Configure an AI agent | [Agent integrations](docs/agent-integrations.md) |
| Record commands, import files, or capture a shell session | [Recording reference](docs/recording.md) |
| Export selected results | [PDF reports](docs/reports.md) |
| Understand provenance and storage | [Architecture](docs/architecture.md) |
| Develop or contribute | [Contributing](CONTRIBUTING.md) |

## Current scope

SaigenBio runs locally. It preserves declared files and observed process facts; it does not automatically discover every dependency or establish scientific correctness. Agents can propose reconstructions from existing files and conversations for review, with evidence and gaps marked. These reconstructions do not become observed execution records.

Workspace setup is available for Codex, Claude Code, OpenCode, and Antigravity. Setup validation and live-agent validation are different; see the integration guide for current evidence and limitations. Hosted collaboration, automatic notebook capture, and environment replay are not implemented.

Report bugs and propose improvements through [GitHub Issues](https://github.com/khan-lab/SaigenBio/issues).
