"""Build and exercise a regular installation entirely outside the source tree."""
import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile

SOURCE = Path(__file__).resolve().parent.parent


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, help="A NEW directory outside this checkout")
    parser.add_argument("--with-quarto", action="store_true", help="Also render and download a PDF and its source bundle")
    args = parser.parse_args()
    tag = datetime.now(timezone.utc).strftime("install-%Y%m%d-%H%M%S")
    target = (args.destination or SOURCE.parent / "SaigenBio-lab" / "installations" / tag).expanduser().resolve()
    require(not target.is_relative_to(SOURCE) and not SOURCE.is_relative_to(target),
            "Choose a separate external directory, not this checkout or one of its parents.")
    require(shutil.which("uv"), "uv is required for the installation check.")
    if args.with_quarto:
        require(shutil.which("quarto"), "Quarto is required for --with-quarto.")
    target.mkdir(parents=True, exist_ok=False)
    logs = target / "logs"
    logs.mkdir()
    workspace = target / "workspace"
    workspace.mkdir()
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    env.pop("SAIGEN_PROJECT", None)
    env.pop("SAIGEN_SESSION", None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["UV_CACHE_DIR"] = str(target / "cache" / "uv")
    env["UV_PYTHON_DOWNLOADS"] = "never"
    report = {"source": str(SOURCE), "workspace": str(workspace), "checks": {},
              "agentDiscovery": "Not exercised: start a fresh agent in workspace."}

    def run(label, argv, cwd=workspace):
        print(label, flush=True)
        result = subprocess.run([str(v) for v in argv], cwd=cwd, env=env,
                                text=True, capture_output=True, timeout=180)
        (logs / (label + ".log")).write_text(result.stdout + result.stderr)
        require(result.returncode == 0, label + " failed; see " + str(logs / (label + ".log")))
        return result.stdout

    try:
        # Build from a copied source tree: even setuptools metadata stays outside SOURCE.
        staging = target / "source-build"
        staging.mkdir()
        for name in ("pyproject.toml", "README.md", "saigen", "web", "skills"):
            src = SOURCE / name
            dst = staging / name
            if src.is_dir():
                shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"))
            else:
                shutil.copy2(src, dst)
        source_hashes = {str(p.relative_to(staging)): hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in staging.rglob("*") if p.is_file()}
        (target / "source-manifest.json").write_text(json.dumps(source_hashes, indent=2) + "\n")
        run("build-wheel", ["uv", "build", "--wheel", "--no-sources", "--python", sys.executable,
                            "--out-dir", target / "wheels", staging])
        wheels = list((target / "wheels").glob("*.whl"))
        require(len(wheels) == 1, "Expected one wheel.")
        wheel = wheels[0]
        runtime = target / "runtime"
        run("create-environment", ["uv", "venv", "--python", sys.executable, runtime])
        python = runtime / "bin" / "python"
        cli = runtime / "bin" / "saigen"
        run("install-wheel", ["uv", "pip", "install", "--python", python, wheel])
        probe = json.loads(run("installed-paths", [python, "-I", "-c",
            "import json,sysconfig,saigen,saigen.server; from pathlib import Path; "
            "print(json.dumps({'module':saigen.__file__,'web':str(saigen.server.WEB),"
            "'data':sysconfig.get_path('data'),"
            "'shell':str(Path(saigen.__file__).parent/'shell'/'hooks.zsh')}))"]))
        require(Path(probe["module"]).resolve().is_relative_to(runtime), "Import escaped the installed environment.")
        require(Path(probe["web"]).resolve().is_relative_to(runtime), "Viewer assets were read from the source checkout.")
        require(Path(probe["shell"]).is_file(), "Packaged shell hooks are missing.")
        report["checks"]["installed_package_and_shell_hooks"] = True
        report["installedPaths"] = probe
        report["wheel"] = {"name": wheel.name, "sha256": hashlib.sha256(wheel.read_bytes()).hexdigest()}
        report["version"] = run("cli-version", [cli, "--version"]).strip()

        bundled_skill = Path(probe["data"]) / "share" / "saigenbio" / "skills" / "saigen-record"
        require((bundled_skill / "SKILL.md").is_file(), "The wheel did not include the recording skill.")
        local_skill = workspace / ".agents" / "skills" / "saigen-record"
        local_skill.parent.mkdir(parents=True)
        shutil.copytree(bundled_skill, local_skill)
        skill = (local_skill / "SKILL.md").read_text()
        require(skill.startswith("---\n") and "name: saigen-record" in skill,
                "Invalid recording skill metadata.")
        require("../../README.md" not in skill, "Installed skill still depends on the source README.")
        report["checks"]["packaged_skill_copied_to_workspace"] = True
        report["skill"] = str(local_skill)

        project = workspace / "projects" / "install-check"
        (project / "data").mkdir(parents=True)
        (project / "scripts").mkdir()
        (project / "data" / "input.tsv").write_text("sample\tcount\nA\t8\nB\t22\nC\t723\n")
        plot_script = project / "scripts" / "count_rows.py"
        plot_script.write_text(
            "import csv, sys\nfrom pathlib import Path\n"
            "with open(sys.argv[1]) as handle:\n"
            "    count = len(list(csv.DictReader(handle, delimiter='\\t')))\n"
            "Path(sys.argv[2]).write_text("
            "'<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 400 160\">'"
            "+'<rect width=\"400\" height=\"160\" fill=\"white\"/>'"
            "+f'<text x=\"30\" y=\"85\" font-size=\"28\">Input rows: {count}</text></svg>')\n")
        run("initialize-project", [cli, "init", "--project", project, "--name", "Packaged installation check"])
        run("import-input", [cli, "snapshot", "--project", project, "--id", "input",
                            "--title", "Synthetic test input", "--file", "data/input.tsv",
                            "--note", "Synthetic fixture for testing installation; not a biological result."])
        flow = json.loads(run("read-import", [cli, "flow", "--project", project]))
        root = next(n for n in flow["states"] if n["id"] == "input")
        input_id = root["artifactIds"][0]
        result = json.loads(run("record-analysis", [
            cli, "run", "--project", project, "--actor", "AI agent", "--from", "input",
            "--title", "Installed CLI output", "--label", "count_rows.py",
            "--reason", "Verify that an installed CLI preserves inputs, scripts, and an SVG outside its source checkout.",
            "--input", "artifact:" + input_id, "--script", "scripts/count_rows.py", "--output", "counts.svg",
            "--", python, "{project}/scripts/count_rows.py", "{input:0}", "counts.svg"]))
        require(result["status"] == "completed", "The installed execution wrapper did not complete.")
        flow = json.loads(run("read-result", [cli, "flow", "--project", project]))
        require(len(flow["states"]) == 2 and len(flow["actions"]) == 1, "Unexpected smoke-test flow.")
        state = next(n for n in flow["states"] if n["id"] == result["state"])
        artifact = flow["artifacts"][state["artifactIds"][0]]
        report["checks"]["installed_cli_records_analysis"] = True

        # A random loopback port avoids the live demo and the report-feature worktree.
        server_log = logs / "viewer.log"
        with server_log.open("w+") as output:
            server = subprocess.Popen([str(cli), "serve", "--project", str(project), "--port", "0"],
                                      cwd=workspace, env=env, stdout=output, stderr=output, text=True)
            try:
                url = None
                for _ in range(100):
                    match = re.search(r"http://127\.0\.0\.1:\d+", server_log.read_text())
                    if match:
                        url = match.group(0)
                        break
                    require(server.poll() is None, "Installed viewer exited; see viewer.log")
                    time.sleep(.05)
                require(url, "Installed viewer did not start.")

                def get(path):
                    with urllib.request.urlopen(url + path, timeout=5) as response:
                        return response.headers.get_content_type(), response.read()

                mime, page = get("/")
                require(mime == "text/html" and b"SaigenBio" in page, "Packaged HTML could not be served.")
                require(len(get("/app.js")[1]) > 1000 and len(get("/style.css")[1]) > 100,
                        "Packaged browser assets are missing.")
                api_flow = json.loads(get("/api/flow")[1])
                require(api_flow["revision"] == flow["revision"], "Viewer served a different project revision.")
                mime, svg = get("/api/artifacts/" + artifact["id"])
                require(mime == "image/svg+xml" and b"Input rows: 3" in svg,
                        "Installed viewer could not serve the real generated plot.")
                report["checks"]["installed_viewer_and_preserved_plot"] = True
                if args.with_quarto:
                    print("render-installed-report", flush=True)
                    session = json.loads(get("/api/session")[1])
                    headers = {"Content-Type": "application/json", "X-Saigen-Token": session["token"]}
                    selection = ["input", result["state"]]
                    payload = json.dumps({"revision": flow["revision"], "selected": selection}).encode()
                    request = urllib.request.Request(url + "/api/reports", data=payload, headers=headers)
                    with urllib.request.urlopen(request, timeout=10) as response:
                        job = json.load(response)
                    deadline = time.monotonic() + 210
                    while job["status"] in {"queued", "rendering"}:
                        require(time.monotonic() < deadline, "Installed PDF report timed out.")
                        time.sleep(.25)
                        request = urllib.request.Request(url + "/api/reports/" + job["id"], headers=headers)
                        with urllib.request.urlopen(request, timeout=10) as response:
                            job = json.load(response)
                    require(job["status"] == "ready", "Installed report failed: " + job.get("error", "unknown"))
                    downloads = target / "downloads"
                    downloads.mkdir()
                    for kind, name in (("pdf", "report.pdf"), ("zip", "source.zip")):
                        request = urllib.request.Request(url + "/api/reports/" + job["id"] + "/" + kind, headers=headers)
                        with urllib.request.urlopen(request, timeout=10) as response:
                            data = response.read()
                        (downloads / name).write_bytes(data)
                    require((downloads / "report.pdf").read_bytes().startswith(b"%PDF-"), "Invalid downloaded PDF.")
                    with zipfile.ZipFile(io.BytesIO((downloads / "source.zip").read_bytes())) as bundle:
                        manifest = json.loads(bundle.read("manifest.json"))
                        require(manifest["selectedOrder"] == selection, "Report selection order changed.")
                        require(manifest["projectRevision"] == flow["revision"], "Report revision changed.")
                        for name, expected in manifest["files"].items():
                            require(hashlib.sha256(bundle.read(name)).hexdigest() == expected, "Source bundle hash mismatch: " + name)
                    require(json.loads(get("/api/flow")[1])["revision"] == flow["revision"], "Report generation changed the analysis graph.")
                    report["checks"]["quarto_pdf_and_source_bundle"] = True
                    report["reportDownloads"] = str(downloads)
            finally:
                server.terminate()
                try:
                    server.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait(timeout=5)

        instructions = [
            "# External installation trial", "",
            "This workspace uses a regular wheel installation. Its CLI and skill do not depend on the source checkout.", "",
            "## Start a fresh agent session", "",
            "From this workspace directory:", "",
            "    source ../runtime/bin/activate", "",
            "Then open a new Codex session in this same directory. The project-local skill is .agents/skills/saigen-record/SKILL.md.",
            "Check that saigen-record appears in the skill selector. Automatic agent discovery has not been tested by this script.", "",
            "Try this prompt:", "",
            "> Use $saigen-record. Create a fresh analysis project at projects/agent-trial. Import the synthetic table at projects/install-check/data/input.tsv and create a small SVG summary through saigen run. Record the input, script, output and reason. Use the installed saigen command and your bundled skill instructions; do not read or edit the original source repository.", "",
            "## View the completed installation check", "",
            "With the environment activated, and port 8767 free:", "",
            "    saigen serve --project projects/install-check --port 8767", "",
            "Open http://127.0.0.1:8767/ . The automated check used a temporary port and stopped its server afterward.", "",
            "## Files", "",
            "- projects/install-check/: synthetic input, script, recorded result and preserved files.",
            "- .agents/skills/saigen-record/: the skill copied from the installed wheel.",
            "- ../installation-check.json: automated results and installed paths.",
            "- ../logs/: build, installation and execution logs.",
            "- ../wheels/, ../runtime/, ../source-build/, ../cache/: this trial's package, environment and build files.", "",
            "To discard this trial later, stop any server or agent using it and remove the entire trial directory. Keep a recorded project's .saigen directory together; its objects are referenced by its history.", ""
        ]
        (workspace / "START.md").write_text("\n".join(instructions))
        report["status"] = "passed"
    except Exception as exc:
        report["status"] = "failed"
        report["error"] = str(exc)
        raise
    finally:
        (target / "installation-check.json").write_text(json.dumps(report, indent=2) + "\n")
        print("Results: " + str(target / "installation-check.json"), flush=True)
    print("Fresh-session workspace: " + str(workspace), flush=True)


if __name__ == "__main__":
    main()
