#!/usr/bin/env bash
# Prepare a demo workspace. Data downloads and analysis happen afterward.
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: bash examples/ecoli/setup.bash [PROJECT_DIRECTORY]

Default: ../SaigenBio-lab/projects/advisor-demo (relative to the current directory).
Requires pixi and saigen on PATH. Creates the environment, folders,
and an empty SaigenBio project. It does not start the viewer or analysis.
Existing Pixi workspaces are rebuilt from their lock file.
USAGE
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi
if (( $# > 1 )); then
  usage >&2
  exit 2
fi

for tool in pixi saigen; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    printf 'Missing required command: %s\n' "$tool" >&2
    exit 1
  fi
done

demo_dir="${1:-../SaigenBio-lab/projects/advisor-demo}"
if [[ -z "$demo_dir" ]]; then
  printf 'Specify a non-empty project directory.\n' >&2
  exit 2
fi
mkdir -p -- "$demo_dir"
cd -- "$demo_dir"

if [[ -f pixi.toml ]]; then
  if [[ ! -f pixi.lock ]]; then
    printf 'Existing pixi.toml has no lock file. Complete its dependencies and lock it before rerunning setup.\n' >&2
    exit 1
  fi
  pixi install --locked
elif [[ -f pyproject.toml || -f pixi.lock ]]; then
  printf 'This directory already has project configuration. Choose a fresh demo directory.\n' >&2
  exit 1
else
  pixi init -c conda-forge -c bioconda
  pixi add fastp bwa samtools bcftools python matplotlib
fi

# Validate the existing environment rather than silently changing its versions.
pixi run --locked python -c '
import shutil
import matplotlib
required = ("fastp", "bwa", "samtools", "bcftools")
missing = [name for name in required if shutil.which(name) is None]
if missing:
    raise SystemExit("Missing tools in the project environment: " + ", ".join(missing))
'

mkdir -p data/reference data/raw scripts
mkdir -p results/qc_A results/qc_B results/alignment
mkdir -p results/calls results/depth5 results/depth10

saigen init --project . --name "Variant filtering demo" >/dev/null

printf '\nDemo workspace ready: %s\n' "$demo_dir"
printf 'From your original directory, start the viewer with:\n'
printf '  saigen serve --project %q\n' "$demo_dir"
printf 'Then open http://127.0.0.1:8765/\n'
