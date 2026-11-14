# Installation

SaigenBio requires Python 3.10 or newer. Its recorder and viewer use the Python standard library. Choose the installation method that fits your existing Python setup; uv is optional.

## Obtain the source

```sh
git clone https://github.com/khan-lab/SaigenBio.git
cd SaigenBio
```

If repository access is restricted, use an account with access. The following methods install this checkout; they do not assume a package-registry release.

## Choose an installation method

Run one of these alternatives from the checkout.

### Python virtual environment and pip

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
```

Activate this environment in terminals where you want to use saigen. The activation command above is for POSIX shells; on Windows PowerShell use .venv\\Scripts\\Activate.ps1.

### An existing environment, including pyenv or Conda

Select or activate your preferred Python 3.10+ environment, then:

```sh
python --version
python -m pip install .
```

pyenv selects the Python interpreter; pip installs SaigenBio into that interpreter's environment. You can use the selected interpreter to create a virtual environment as shown above. Avoid installing into an operating-system-managed Python environment.

### pipx

If you already use pipx for command-line applications:

```sh
pipx install .
```

### uv

If you already use uv:

```sh
uv tool install .
```

pipx and uv tool installations provide an isolated application environment. Ensure their executable directory is on PATH.

## Verify and continue

```sh
saigen --version
saigen init --help
```

The init help should include --agent, --port, --permissions, --non-interactive, and --start-viewer. These options confirm that the installed command supports the setup interview; the version number may be shared by multiple source revisions. If the command is unavailable, activate the environment containing the installation or check your tool manager's PATH setup. Then follow the [first-run walkthrough](getting-started.md).

Your scientific tools can live in separate environments. SaigenBio does not install aligners, variant callers, or plotting packages automatically.

## Optional features

- PDF reports require Quarto with its bundled Typst engine on PATH.
- Recorded human shell sessions require zsh on POSIX.
- AI-driven analysis requires a separately installed agent; see [Agent integrations](agent-integrations.md).

## Updating

From your clean source checkout, update to the merged code:

```sh
cd /path/to/SaigenBio
git switch main
git pull --ff-only
```

Reinstall using the same environment or tool manager as before. For a uv tool installation:

```sh
uv tool install --reinstall --no-cache .
saigen init --help
```

The explicit reinstall replaces the installed code even when the source version number has not changed; --no-cache also avoids reusing a cached build. Run the command from the checkout you just updated, not another older clone. Pulling commits does not by itself update a regular installed copy.

For other installation methods, activate/select the original environment and use its corresponding command:

| Installation | Reinstall from the updated checkout |
| --- | --- |
| Virtual environment, pyenv, or Conda with pip | `python -m pip install --force-reinstall --no-cache-dir .` |
| pipx | `pipx install --force .` |

Verify the new init options after reinstalling. Your analysis history does not need to be deleted or reinitialized to upgrade the software.

Restart the viewer to load updated Python code and reload the browser. Workspace-local skills are copies: [refresh existing instructions](agent-integrations.md#refresh-existing-workspace-instructions) while preserving customizations. Setup refuses to overwrite customized instruction files. If the installed CLI moves to another environment, update its path in saigen-workspace.json. To start an independent analysis instead, follow [Restart with a fresh analysis](getting-started.md#restart-with-a-fresh-analysis).

## The init interview is missing

If init help lists only --project, --actor, and --name, the command is an older installed copy. In a POSIX shell, inspect which executable wins on PATH:

```sh
command -v saigen
type -a saigen
```

Reinstall from the intended checkout using the installation method above. If multiple saigen commands are listed, activate the intended environment or correct PATH so its executable is selected. For zsh, `rehash` refreshes command lookup after changing executable locations. Then check `saigen init --help` again.

The interview runs when both input and output are attached to a terminal and --non-interactive is absent. Run init directly in a terminal rather than through a pipe or an agent's non-interactive command runner. Supplying all settings as flags still skips their questions.

An older init can create an empty project and print JSON without interviewing you. Once a project exists, the new init also retains it rather than restarting setup. To experience the interview from the beginning, use a new empty directory as described in the [fresh-start walkthrough](getting-started.md#restart-with-a-fresh-analysis); do not delete recorded evidence just to trigger setup.

For editable installations and software checks, see [Contributing](../CONTRIBUTING.md).
