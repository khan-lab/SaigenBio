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
    parser.add_argument("--agent", choices=["codex","claude","opencode","antigravity"], default="codex")
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
        for name in ("pyproject.toml", "README.md", "saigen", "ui", "skills"):
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
            "print(json.dumps({'module':saigen.__file__,'ui':str(saigen.server.UI),"
            "'data':sysconfig.get_path('data'),"
            "'shell':str(Path(saigen.__file__).parent/'shell'/'hooks.zsh')}))"]))
        require(Path(probe["module"]).resolve().is_relative_to(runtime), "Import escaped the installed environment.")
        require(Path(probe["ui"]).resolve().is_relative_to(runtime), "Viewer assets were read from the source checkout.")
        require(Path(probe["shell"]).is_file(), "Packaged shell hooks are missing.")
        report["checks"]["installed_package_and_shell_hooks"] = True
        report["installedPaths"] = probe
        report["wheel"] = {"name": wheel.name, "sha256": hashlib.sha256(wheel.read_bytes()).hexdigest()}
        report["version"] = run("cli-version", [cli, "--version"]).strip()

        bundled_skill = Path(probe["data"]) / "share" / "saigenbio" / "skills" / "saigen-record"
        require((bundled_skill / "SKILL.md").is_file(), "The wheel did not include the recording skill.")
        skill_folder = {"claude":".claude", "opencode":".opencode"}.get(args.agent, ".agents")
        local_skill = workspace / skill_folder / "skills" / "saigen-record"
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
        run("publish-plan", [cli, "plan", "--project", project, "--from", "input",
                             "--id", "summary_plan", "--title", "Installed CLI output",
                             "--expect", "An SVG showing the number of input rows.",
                             "--details", "Count the rows in the preserved sample table.",
                             "--requires", "Review the synthetic input before counting.",
                             "--output", "counts.svg"])
        proposed = json.loads(run("read-plan", [cli, "flow", "--project", project]))
        require(not proposed["actions"] and
                next(n for n in proposed["states"] if n["id"] == "summary_plan")["status"] == "planned",
                "A proposed result must not create an execution edge.")
        result = json.loads(run("record-analysis", [
            cli, "run", "--project", project, "--plan", "summary_plan", "--approved", "--actor", "AI agent", "--from", "input",
            "--title", "Installed CLI output", "--label", "count_rows.py",
            "--reason", "Verify that an installed CLI preserves inputs, scripts, and an SVG outside its source checkout.",
            "--input", "artifact:" + input_id, "--script", "scripts/count_rows.py", "--output", "counts.svg",
            "--", python, "{project}/scripts/count_rows.py", "{input:0}", "counts.svg"]))
        require(result["status"] == "completed" and result["state"] == "summary_plan", "The installed execution wrapper did not finalize the proposed state.")
        flow = json.loads(run("read-result", [cli, "flow", "--project", project]))
        require(len(flow["states"]) == 2 and len(flow["actions"]) == 1, "Unexpected smoke-test flow.")
        state = next(n for n in flow["states"] if n["id"] == result["state"])
        proposal = next(n for n in proposed["states"] if n["id"] == "summary_plan")
        for key in ("expectedSummary", "planDetails", "planRequires", "expectedFiles", "planParents"):
            require(state["plan"][key] == proposal[key], "Original plan lost " + key)
        artifact = flow["artifacts"][state["artifactIds"][0]]
        report["checks"]["installed_cli_records_analysis"] = True
        report["checks"]["planned_state_finalized_without_duplicate"] = True
        report["checks"]["original_plan_details_preserved"] = True

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
                require(all(len(get(asset)[1]) > 100 for asset in ("/geometry.js", "/paths.js")), "Installed UI modules are missing")
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

        run("setup-agent-workspace", [cli, "setup", "--workspace", workspace,
            "--agent", args.agent, "--analysis-project", "projects/agent-demo-01",
            "--input", "projects/install-check/data/input.tsv",
            "--viewer", "http://127.0.0.1:8767/"])
        report["agent"] = args.agent
        report["checks"]["agent_workspace_setup"] = True

        instructions = [
            "# External installation trial", "",
            "This workspace uses a regular wheel installation. Its CLI and skill do not depend on the source checkout.", "",
            "## Start a fresh agent session", "",
            "From this workspace directory:", "",
            "    source ../runtime/bin/activate", "",
            f"Then open a new {args.agent} session in this same directory. The project-local skill is {skill_folder}/skills/saigen-record/SKILL.md.",
            "Check that saigen-record appears in the skill selector. Automatic agent discovery has not been tested by this script.", "",
            "The generated agent instructions select projects/agent-demo-01 through saigen-workspace.json.", "",
            "Before opening the agent, initialize the project and leave its viewer running in a separate terminal:", "",
            "    saigen init --project projects/agent-demo-01 --name 'Fresh agent demo'",
            "    saigen serve --project projects/agent-demo-01 --port 8767", "",
            "Open http://127.0.0.1:8767/. Then start a fresh agent in this workspace with the runtime activated.", "",
            "Try this prompt (no explicit skill invocation):", "",
            "> I want to explore this sample-count table. First, plot the count for each sample in sample-name order and tell me what stands out. Let us inspect that before deciding what to do next.", "",
            "## View the completed installation check", "",
            "To inspect the automated fixture separately, with the environment activated and port 8768 free:", "",
            "    saigen serve --project projects/install-check --port 8768", "",
            "Open http://127.0.0.1:8768/ . The automated check used a temporary port and stopped its server afterward.", "",
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
