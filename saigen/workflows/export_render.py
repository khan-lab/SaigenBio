"""Render reviewed plans into native workflow entry points and a portable runner."""
import json


RUNNER = r'''"""Run one exported argv command in an isolated working directory."""
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

bundle = Path(__file__).resolve().parent
key, *arguments = sys.argv[1:]
step = json.loads((bundle / "configuration.json").read_text())[key]
size = len(step["inputs"])
destinations = [Path(p).resolve() for p in arguments[size:]]
inputs = [str(Path(p).resolve()) for p in arguments[:size]]
scripts = [str(bundle / key / entry["name"]) for entry in step["scripts"]]
if len(destinations) != len(step["outputs"]) or len(inputs) != size:
    raise SystemExit("Wrong number of step inputs or outputs")

def substitute(match):
    sources = inputs if match[1] == "input" else scripts
    return sources[int(match[2])]

argv = [re.sub(r"\{(input|script):(\d+)\}", substitute, arg) for arg in step["argv"]]
with tempfile.TemporaryDirectory(prefix="saigen-step-") as tmp:
    work = Path(tmp)
    for output in step["outputs"]:
        (work / output["name"]).parent.mkdir(parents=True, exist_ok=True)
    if step["stdout"]:
        with (work / step["stdout"]).open("wb") as stream:
            subprocess.run(argv, cwd=work, check=True, stdout=stream)
    else:
        subprocess.run(argv, cwd=work, check=True)
    for output, destination in zip(step["outputs"], destinations):
        source = work / output["name"]
        if not source.is_file():
            raise SystemExit(f"Missing expected result {output['name']}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
'''


def nextflow(plan):
    processes, calls = [], []
    channels = {entry["path"]: f'channel.value(file("${{projectDir}}/{entry["path"]}", checkIfExists: true))'
                for entry in plan["inputs"]}
    for step in plan["steps"]:
        key = step["key"]
        inputs = [f"    path dep{i}, stageAs: 'deps/{i}/*'" for i in range(len(step["inputs"]))]
        outputs = [f"    path '{out['path']}', emit: result{i}" for i, out in enumerate(step["outputs"])]
        args = [f'"${{dep{i}}}"' for i in range(len(inputs))]
        args.extend(f'"{out["path"]}"' for out in step["outputs"])
        processes.extend([f"process {key} {{", """    publishDir projectDir, mode: 'copy', overwrite: true""",
                          "    input:", "    path bundle, stageAs: 'bundle'", *inputs, "",
                          "    output:", *outputs, "", "    script:", '    """',
                          f"    python3 bundle/run_step.py {key} " + " ".join(args), '    """', "}", ""])
        calls.append(f"    {key}(" + ", ".join(["bundle", *(channels[path] for path in step["inputs"])]) + ")")
        for i, output in enumerate(step["outputs"]):
            channels[output["path"]] = f"{key}.out.result{i}"
    return "\n".join(["nextflow.enable.dsl=2", "", *processes, "workflow {",
                       "    bundle = channel.value(file(\"${projectDir}/bundle\", checkIfExists: true))",
                       *calls, "}", ""])


def snakemake(plan):
    targets = list(dict.fromkeys(path for target in plan["targets"] for path in target["paths"]))
    lines = ["rule all:", "    input: " + json.dumps(targets), ""]
    for step in plan["steps"]:
        key = step["key"]
        files = ["bundle/run_step.py", "bundle/configuration.json",
                 *(f"bundle/{key}/{script['name']}" for script in step["scripts"])]
        lines.extend([f"rule {key}:", f"    input: data={json.dumps(step['inputs'])}, bundle={json.dumps(files)}",
                      f"    output: {json.dumps([entry['path'] for entry in step['outputs']])}",
                      f'    shell: "python3 bundle/run_step.py {key} {{input.data:q}} {{output:q}}"', ""])
    return "\n".join(lines)
