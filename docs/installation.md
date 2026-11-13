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
saigen --help
```

If the command is unavailable, activate the environment containing the installation or check your tool manager's PATH setup. Then follow [Getting started](getting-started.md).

Your scientific tools can live in separate environments. SaigenBio does not install aligners, variant callers, or plotting packages automatically.

## Optional features

- PDF reports require Quarto with its bundled Typst engine on PATH.
- Recorded human shell sessions require zsh on POSIX.
- AI-driven analysis requires a separately installed agent; see [Agent integrations](agent-integrations.md).

## Updating

Update the checkout, then reinstall using the same method. For pip, run python -m pip install --upgrade .; for pipx use pipx install --force .; for uv use uv tool install --force ..

Restart the viewer to load updated Python code and reload the browser. Workspace-local skills are copies: review changes when updating existing instructions. Setup refuses to overwrite differing files. If the installed CLI moves to another environment, update its path in saigen-workspace.json.

For editable installations and software checks, see [Contributing](../CONTRIBUTING.md).
