"""Selected-state reports. Recorded text is data; only Quarto/Typst is executed."""
from __future__ import annotations
import hashlib
import json
import re
import shlex
import shutil
import subprocess
import threading
import uuid
import zipfile
from pathlib import Path
from xml.etree import ElementTree
from .store import RecordError, Conflict, now
from .report_templates import DEFAULT_TEMPLATE, template_definition, compose, literal, code_cell, table_cell

FORMATS = {"image/svg+xml": ".svg", "image/png": ".png", "image/jpeg": ".jpg"}
RENDER = ["quarto", "render", "report.qmd", "--to", "typst", "--output", "report.pdf", "--no-execute"]


def sha(data):
    return hashlib.sha256(data).hexdigest()


class Reports:
    def __init__(self, store):
        self.store = store
        self.jobs = {}
        self.lock = threading.Lock()

    def reserve(self, selection, revision, template, status):
        template_definition(template)
        if not isinstance(selection, list) or not 1 <= len(selection) <= 50 or any(not isinstance(x, str) for x in selection) or len(set(selection)) != len(selection):
            raise RecordError("Select 1–50 distinct states in presentation order")
        flow = self.store.flow()
        if flow["revision"] != revision:
            raise Conflict("The project changed. Review the selection and create the report again.")
        if any(x not in {n["id"] for n in flow["states"]} for x in selection):
            raise RecordError("Unknown selected state")
        with self.lock:
            if any(j["status"] in {"queued", "rendering", "preparing"} for j in self.jobs.values()):
                raise RecordError("A report is already rendering. Wait for it to finish.")
            ident = uuid.uuid4().hex
            self.jobs[ident] = {"id": ident, "status": status, "revision": revision}
        return ident, flow

    def start(self, selection, revision, template=DEFAULT_TEMPLATE):
        ident, flow = self.reserve(selection, revision, template, "queued")
        threading.Thread(target=self.build, args=(ident, flow, selection, template), daemon=True).start()
        return self.status(ident)

    def preview(self, selection, revision, template=DEFAULT_TEMPLATE):
        ident, flow = self.reserve(selection, revision, template, "preparing")
        folder = self.store.home / "reports" / ident
        try:
            folder.mkdir(parents=True)
            (folder / "figures").mkdir()
            manifest = self.prepare(folder, flow, selection, template)
            with self.lock:
                self.jobs[ident].update(status="preview", template=manifest["template"], outline=manifest["outline"], warnings=manifest["warnings"],
                    _preparedFiles={**manifest["files"], "manifest.json": sha((folder / "manifest.json").read_bytes())})
            return self.status(ident)
        except Exception as exc:
            with self.lock:
                self.jobs[ident]["status"] = "failed"
            if isinstance(exc, RecordError):
                raise
            raise RecordError("Could not prepare this report; check preserved evidence and available disk space") from exc

    def render_preview(self, ident, revision):
        with self.lock:
            job = self.jobs.get(ident)
            if not job or job["status"] != "preview":
                raise RecordError("Preview this report before exporting")
            if job["revision"] != revision:
                raise Conflict("The preview revision does not match")
            if any(j["status"] in {"queued", "rendering", "preparing"} for j in self.jobs.values()):
                raise RecordError("A report is already rendering. Wait for it to finish.")
            job["status"] = "queued"
        threading.Thread(target=self.build, args=(ident, None, None, DEFAULT_TEMPLATE, True), daemon=True).start()
        return self.status(ident)

    def status(self, ident):
        with self.lock:
            if ident not in self.jobs:
                raise RecordError("Unknown report (report links last for this server session)")
            return {key:value for key,value in self.jobs[ident].items() if not key.startswith("_")}

    def file(self, ident, kind):
        job = self.status(ident)
        if job["status"] != "ready" or kind not in {"pdf", "zip"}:
            raise RecordError("Report download is not ready")
        return self.store.home / "reports" / ident / ("report.pdf" if kind == "pdf" else "source.zip")

    def build(self, ident, flow, selection, template=DEFAULT_TEMPLATE, prepared=False):
        folder = self.store.home / "reports" / ident
        try:
            with self.lock:
                self.jobs[ident]["status"] = "rendering"
            if not prepared:
                folder.mkdir(parents=True)
                (folder / "figures").mkdir()
                self.prepare(folder, flow, selection, template)
            if prepared:
                expected = self.jobs[ident].get("_preparedFiles")
                if expected is None:
                    raise RecordError("Preview evidence is unavailable; prepare a new preview")
                for name, expected_hash in expected.items():
                    if sha((folder / name).read_bytes()) != expected_hash:
                        raise RecordError("Prepared report changed; prepare a new preview before exporting")
            executable = shutil.which("quarto")
            if not executable:
                raise RecordError("Quarto is unavailable. Install Quarto with its bundled Typst engine and retry.")
            version = subprocess.run([executable, "--version"], cwd=folder, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=15)
            result = subprocess.run([executable, *RENDER[1:]], cwd=folder, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180)
            (folder / "render.log").write_bytes(result.stdout)
            if result.returncode or not (folder / "report.pdf").is_file():
                raise RecordError("Quarto could not render this report. The local report folder contains render.log; check the saved figures and Quarto installation.")
            manifest = json.loads((folder / "manifest.json").read_text())
            manifest["quartoVersion"] = version.stdout.decode("utf-8", errors="replace").strip()[:200]
            manifest["renderedAt"] = now()
            manifest["files"]["report.pdf"] = sha((folder / "report.pdf").read_bytes())
            (folder / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
            with zipfile.ZipFile(folder / "source.zip", "w", zipfile.ZIP_DEFLATED) as bundle:
                for name in ["manifest.json", *sorted(manifest["files"])]:
                    bundle.write(folder / name, name)
            with self.lock:
                self.jobs[ident].update(status="ready", warnings=manifest["warnings"])
        except Exception as exc:
            message = str(exc) if isinstance(exc, RecordError) else "Report generation failed; check the local Quarto installation and available disk space."
            with self.lock:
                self.jobs[ident].update(status="failed", error=message)

    def prepare(self, folder, flow, selection, template=DEFAULT_TEMPLATE):
        template = template_definition(template)
        states = {n["id"]: n for n in flow["states"]}
        selected = [states[x] for x in selection]
        actions = [a for a in flow["actions"] if a["to"] in selection]
        # Alias paths recursively in all exported records and free text. File contents
        # are preserved unchanged, so their own embedded labels may contain paths.
        roots = {str(self.store.root): "{project}"}
        for item in selected + actions:
            repo = item.get("code", {}).get("repository")
            if repo and repo not in roots:
                roots[repo] = "{source:%d}" % len(roots)
        aliases = {}
        for ar in flow["artifacts"].values():
            if ar.get("sourcePath"):
                aliases[ar["sourcePath"]] = "{artifact:" + ar["sha256"][:8] + "}/" + ar["name"]
            if ar.get("sha256"):
                aliases[str(self.store.home / "objects" / ar["sha256"])] = "{artifact:" + ar["sha256"][:8] + "}/" + ar["name"]
        for action in actions:
            cwd = action.get("cwd", "")
            if "/.saigen/runs/" in cwd:
                original = cwd.split("/.saigen/runs/")[0]
                roots.setdefault(original, "{project}")
                for ar in flow["artifacts"].values():
                    aliases[original + "/.saigen/objects/" + ar["sha256"]] = "{artifact:" + ar["sha256"][:8] + "}/" + ar["name"]
            argv = action.get("argv") or action.get("argvTemplate") or []
            if argv and argv[0].startswith("/"):
                aliases[argv[0]] = "{tool}/" + Path(argv[0]).name
        def clean(value):
            if isinstance(value, dict):
                return {k: clean(v) for k, v in value.items()}
            if isinstance(value, list):
                return [clean(v) for v in value]
            if not isinstance(value, str):
                return value
            for path in sorted(aliases, key=len, reverse=True):
                value = value.replace(path, aliases[path])
            for root in sorted(roots, key=len, reverse=True):
                value = value.replace(root, roots[root])
            return re.sub(r'(?<![\w}:/])(?:/[\w.~+%:@=-]+){2,}', lambda m: "{external}/" + Path(m.group()).name, value)
        def txt(v):
            return literal(clean(v))
        ids = set()
        for n in selected:
            ids.update(n.get("artifactIds", []))
        for a in actions:
            ids.update(a.get("inputArtifacts", []))
            ids.update(a.get("logs", []))
            ids.update(a.get("code", {}).get("scriptArtifacts", []))
            ids.update(a.get("environment", {}).get("capturedFiles", []))
        workflow_context = {"proposals": {}, "runs": {}}
        for node in selected:
            for group, field in (("proposals", "workflowProposal"), ("runs", "workflowRun")):
                key = node.get(field)
                record = flow.get("workflows", {}).get(group, {}).get(key)
                if record:
                    workflow_context[group][key] = record
                    if group == "proposals":
                        ids.update(b["artifactId"] for b in record["spec"]["inputBindings"])
        records = {key: flow["artifacts"][key] for key in ids if key in flow["artifacts"]}
        parent_ids = dict.fromkeys([p for a in actions for p in a.get("from", [])] +
                                   [p for n in selected for p in n.get("planParents", [])])
        context = [{"id": key, "title": states[key]["title"]}
                   for key in parent_ids if key not in selection and key in states]
        snapshot = clean({"project": flow["project"], "revision": flow["revision"], "selectedOrder": selection, "states": selected, "actions": actions, "artifacts": records, "omittedParentContext": context, "workflows": workflow_context})
        manifest = {"schemaVersion": 1, "createdAt": now(), "projectRevision": flow["revision"], "selectedOrder": selection, "orderMeaning": "Presentation order only; no execution or dependency order inferred", "renderer": "Quarto with bundled Typst", "renderArgv": RENDER, "figures": [], "artifacts": {}, "warnings": [], "files": {}}
        model = {"project": clean(flow["project"]), "revision": flow["revision"], "states": [], "warnings": manifest["warnings"]}
        manifest["template"] = template
        for aid in sorted(ids - records.keys()):
            manifest["warnings"].append("Missing artifact record: " + aid)
        shown_scripts = {}
        shown_notebook_scripts = {}
        total = 0
        for index, n in enumerate(selected, 1):
            state = {"title": clean(n["title"]), "status": n.get("status", "unknown"),
                     **{key: [] for key in ("overview", "method_summary", "scripts", "excerpts", "commands", "execution", "previews", "inventory", "environment")}}
            model["states"].append(state)
            body = state["overview"]
            status = n.get("status")
            if status != "completed":
                body += [txt(status) + (' · not run' if status == 'planned' else ' · earlier execution not recorded' if status == 'imported' else ''), '']
            incoming = [a for a in actions if a["to"] == n["id"]]
            note = n.get("note") or ""
            if status == 'planned':
                parents = [states[p]['title'] + (' (outside selection)' if p not in selection else '') for p in n.get('planParents', []) if p in states]
                if parents:
                    body += ['Planned inputs: ' + txt(', '.join(parents)), '']
                expected = n.get('expectedSummary') or note
                if expected:
                    body += ['Expected result: ' + txt(expected), '']
                if n.get('planDetails'):
                    body += ['Proposed method: ' + txt(n['planDetails']), '']
                if n.get('expectedFiles'):
                    body += ['Expected files (not proof of production): ' + txt(', '.join(n['expectedFiles'])), '']
                if n.get('planRequires'):
                    body += ['Prerequisite (descriptive, not enforced): ' + txt(n['planRequires']), '']
                if note == expected:
                    note = ''
            if note:
                body += [txt(note), '']
            method = state["method_summary"]
            proposal = flow.get("workflows", {}).get("proposals", {}).get(n.get("workflowProposal"))
            if proposal:
                spec = proposal["spec"]
                stage = next((v for v in spec["stages"] if v["key"] == n.get("workflowStage")), {})
                declared = stage.get("method", {})
                method += ["Declared tool: " + txt(declared.get("tool", "Not recorded")) + " · Engine: " + txt(spec["engine"]["name"] + " " + spec["engine"]["version"]) + " (proposal)", "",
                           txt(declared.get("summary", "Method explanation not recorded.")), "",
                           "Supplied parameters (pipeline defaults remain in source): " + txt(json.dumps(spec["configuration"].get("parameters", {}), sort_keys=True)), "",
                           "Stage connections follow the saved mapping; they do not establish observed file-level dependencies.", ""]
            elif status != "planned":
                explanations = [(a.get("code", {}).get("explanation") or {}) for a in incoming]
                for explanation in explanations:
                    if explanation.get("summary"):
                        method += [txt(explanation["summary"]), "", "Explanation recorded by " + txt(explanation.get("recordedBy", "Not recorded")), ""]
                if not any(v.get("summary") for v in explanations):
                    method += ["Method explanation not recorded.", ""]
            for action in incoming:
                body = state["overview"]
                parents = [states[p]["title"] + (" (outside selection)" if p not in selection else "") for p in action.get("from", []) if p in states]
                if parents:
                    body += ['Uses: ' + txt(', '.join(parents)), '']
                reason = action.get("reason")
                if reason and reason.strip() != note.strip():
                    body += [txt(reason), '']
                if action.get("annotation"):
                    body += ['Note: ' + txt(action['annotation']), '']
                body = state["scripts"]
                scripts = action.get("code", {}).get("scriptArtifacts", [])
                for aid in scripts:
                    before = len(body)
                    excerpts = []
                    preferred = None
                    ar = flow['artifacts'].get(aid)
                    try:
                        if not ar or ar.get('storage') != 'preserved':
                            raise RecordError('preserved copy unavailable')
                        if ar['size'] > 1024 * 1024:
                            raise RecordError('script exceeds 1 MB display limit')
                        data = self.store.artifact_path(ar).read_bytes()
                        if sha(data) != ar['sha256']:
                            raise RecordError('script hash mismatch')
                        source = data.decode('utf-8')
                        for excerpt in action.get("code", {}).get("explanation", {}).get("excerpts", []):
                            if excerpt.get("artifactId") != aid:
                                continue
                            first, last = excerpt.get("start"), excerpt.get("end")
                            lines = source.splitlines()
                            if type(first) is not int or type(last) is not int or not 1 <= first <= last <= len(lines) or last-first >= 40 or excerpt.get("text") != "\n".join(lines[first-1:last]):
                                manifest["warnings"].append(clean(ar["name"]) + ": selected excerpt does not match preserved source; full script retained")
                                continue
                            excerpts += [txt(ar["name"]) + " · Lines " + str(first) + "–" + str(last), "", "Excerpt selected by " + txt(action["code"]["explanation"].get("recordedBy", "Not recorded")), ""] + code_cell(clean(excerpt["text"]))
                        key = ar['sha256']
                        if key in shown_scripts:
                            body += [txt(ar['name']) + ' · shown in section ' + str(shown_scripts[key]), '']
                        else:
                            shown_scripts[key] = index
                            language = {'.py': 'python', '.r': 'r', '.sh': 'bash', '.js': 'javascript'}.get(Path(ar['name']).suffix.lower(), '')
                            body += [txt(ar['name']), ''] + code_cell(clean(source), language)
                        if excerpts:
                            preferred = excerpts
                        elif key in shown_notebook_scripts:
                            preferred = [txt(ar['name']) + ' · shown in section ' + str(shown_notebook_scripts[key]), '']
                        else:
                            shown_notebook_scripts[key] = index
                            language = {'.py':'python', '.r':'r', '.sh':'bash', '.js':'javascript'}.get(Path(ar['name']).suffix.lower(), '')
                            preferred = [txt(ar['name']), ''] + code_cell(clean(source), language)
                    except (RecordError, OSError, UnicodeError) as exc:
                        warning = (ar['name'] if ar else aid) + ': ' + str(exc)
                        manifest['warnings'].append(clean(warning))
                        body += ['Script unavailable: ' + txt(warning), '']
                    state["excerpts"] += preferred if preferred is not None else body[before:]
                body = state["commands"]
                argv = action.get('argv') or action.get('argvTemplate') or []
                command = shlex.join(clean(argv)) if argv else clean(action.get('command') or '')
                if command:
                    if not scripts:
                        body += ['Script contents not recorded.', '']
                    body += code_cell(command, 'bash')
                body = state["execution"]
                if action.get('status') != 'completed' or action.get('exitCode') not in (None, 0):
                    body += [txt(action.get('status')) + ' · Exit ' + txt(str(action.get('exitCode', 'unknown'))), '']
                if action.get('error'):
                    body += ['Error: ' + txt(action['error']), '']
            body = state["commands"]
            for command in (n.get('terminal') or {}).get('commands', []):
                body += code_cell(clean(command.get('command', '')), 'bash')
                body += ['Shell activity · ' + txt(command.get('status')) + ' · association with saved outputs does not establish file dependencies.', '']
            figures = []
            for aid in n.get("artifactIds", []):
                ar = flow["artifacts"].get(aid)
                if not ar:
                    manifest["warnings"].append("Missing artifact record: " + aid)
                    continue
                manifest["artifacts"][aid] = clean({k: ar.get(k) for k in ["name", "sha256", "size", "storage", "sourcePath"]})
                if ar.get("mime") not in FORMATS:
                    continue
                try:
                    if ar["storage"] != "preserved":
                        raise RecordError("external reference; not read")
                    if ar["size"] > 20 * 1024 * 1024 or total + ar["size"] > 100 * 1024 * 1024:
                        raise RecordError("figure size limit exceeded")
                    data = self.store.artifact_path(ar).read_bytes()
                    if sha(data) != ar["sha256"]:
                        raise RecordError("figure changed during copy")
                    if ar["mime"] == "image/svg+xml":
                        if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
                            raise RecordError("SVG contains external declarations")
                        tree = ElementTree.fromstring(data)
                        for el in tree.iter():
                            if el.tag.split('}')[-1] in {"script", "foreignObject", "image", "use"} or any(k.split('}')[-1] == 'href' or 'url(' in v.lower() or '@import' in v.lower() for k, v in el.attrib.items()) or (el.text and ('url(' in el.text.lower() or '@import' in el.text.lower())):
                                raise RecordError("SVG contains unsupported embedded or linked content")
                    total += len(data)
                    name = "figures/" + ar["sha256"] + FORMATS[ar["mime"]]
                    (folder / name).write_bytes(data)
                    if name not in manifest["figures"]:
                        manifest["figures"].append(name)
                    manifest["files"][name] = sha(data)
                    figures += ['![' + txt(ar["name"]) + '](' + name + '){width=100%}', '']
                except (RecordError, OSError, ElementTree.ParseError) as exc:
                    warning = clean(ar["name"]) + ": " + str(exc)
                    manifest["warnings"].append(warning)
                    figures += ['Figure unavailable: ' + literal(warning), '']
            body = state["previews"]
            body += figures
            tables = [flow['artifacts'][aid] for aid in n.get('artifactIds', []) if aid in flow['artifacts'] and flow['artifacts'][aid].get('tablePreview')]
            for ar in tables:
                preview = clean(ar['tablePreview'])
                columns = preview.get('columns', [])
                if not columns:
                    continue
                body += [txt(ar['name']), '', '| ' + ' | '.join(table_cell(c) for c in columns) + ' |', '| ' + ' | '.join('---' for _ in columns) + ' |']
                for row in preview.get('rows', []):
                    values = (row + [''] * len(columns))[:len(columns)]
                    body += ['| ' + ' | '.join(table_cell(c) for c in values) + ' |']
                body += ['', 'Saved table preview · excerpt; rows, columns, or cell text may be truncated.', '']
            if not figures and not tables and not note and status != "planned":
                body += ['No saved preview or summary is available.', '']
            artifact_groups = {"Declared input files": [aid for a in incoming for aid in a.get("inputArtifacts", []) if flow["artifacts"].get(aid, {}).get("role") not in {"code", "environment", "log"}],
                               "Preserved files" if n.get("origin") == "terminal" else "Imported inputs" if status == "imported" else "Produced files": n.get("artifactIds", [])}
            if status == "planned":
                artifact_groups.pop("Produced files", None)
            for label, artifact_ids in artifact_groups.items():
                state["inventory"] += ["### " + label, ""]
                for aid in dict.fromkeys(artifact_ids):
                    ar = flow["artifacts"].get(aid)
                    state["inventory"] += [txt(ar["name"] + " · SHA-256 " + ar["sha256"] + " · " + ar["storage"]) if ar else "Missing artifact record: " + txt(aid), ""]
                if not artifact_ids:
                    state["inventory"] += ["No files recorded.", ""]
            if proposal:
                state["inventory"] += ["Workflow input bindings describe the whole workflow, not observed stage-level consumption.", ""]
            if n.get("expectedFiles"):
                state["inventory"] += ["Expected files (not proof of production): " + txt(", ".join(n["expectedFiles"])), ""]
            if n.get("origin") == "terminal":
                state["overview"] += ["Saved checkpoint: selected files do not establish production by individual shell commands.", ""]
            for action in incoming:
                state["environment"] += code_cell(json.dumps(clean({"status": action.get("status"), "exitCode": action.get("exitCode"), "recordedBy": action.get("writtenBy"), "performedBy": action.get("performedBy"), "startedAt": action.get("startedAt"), "finishedAt": action.get("finishedAt"), "code": {k:v for k,v in action.get("code", {}).items() if k != "explanation"}, "environment": action.get("environment", {})}), indent=2), "json")
            if not incoming:
                state["environment"] += ["No wrapped execution record; software environment not established.", ""]
        manifest["artifacts"] = {aid: clean({k:ar.get(k) for k in ("name", "sha256", "size", "role", "storage", "sourcePath")}) for aid,ar in records.items()}
        source, outline = compose(model, template)
        manifest["outline"] = outline
        for name, data in {'_quarto.yml': 'project:\n  type: default\nexecute:\n  enabled: false\n', 'report.qmd': source, 'report-template.json': json.dumps(template, indent=2) + '\n', 'snapshot.json': json.dumps(snapshot, indent=2) + '\n'}.items():
            (folder / name).write_text(data, encoding='utf-8')
            manifest['files'][name] = sha((folder / name).read_bytes())
        (folder / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        return manifest
