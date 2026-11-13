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

FORMATS = {"image/svg+xml": ".svg", "image/png": ".png", "image/jpeg": ".jpg"}
RENDER = ["quarto", "render", "report.qmd", "--to", "typst", "--output", "report.pdf", "--no-execute"]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def literal(value):
    # Escape all Markdown syntax, including executable fences, raw blocks and links.
    return re.sub(r'([!"#$%&\'()*+,\-./:;<=>?@\[\\\]^_`{|}~])', r'\\\1', str(value or ""))


def code_cell(value, language=""):
    # Plain language fences are display-only; never use Quarto executable braces.
    value = str(value)
    fence = "`" * max(3, max((len(m.group()) + 1 for m in re.finditer(r"`+", value)), default=3))
    return [fence + language, value, fence, ""]


def table_cell(value):
    return literal(value).replace("\n", " ").replace("\r", " ")


class Reports:
    def __init__(self, store):
        self.store = store
        self.jobs = {}
        self.lock = threading.Lock()

    def start(self, selection, revision):
        if not isinstance(selection, list) or not 1 <= len(selection) <= 50 or any(not isinstance(x, str) for x in selection) or len(set(selection)) != len(selection):
            raise RecordError("Select 1–50 distinct states in presentation order")
        flow = self.store.flow()  # one SQLite row read: all records share this revision
        if flow["revision"] != revision:
            raise Conflict("The project changed. Review the selection and create the report again.")
        states = {n["id"]: n for n in flow["states"]}
        if any(x not in states for x in selection):
            raise RecordError("Unknown selected state")
        with self.lock:
            if any(j["status"] in {"queued", "rendering"} for j in self.jobs.values()):
                raise RecordError("A report is already rendering. Wait for it to finish.")
            ident = uuid.uuid4().hex
            self.jobs[ident] = {"id": ident, "status": "queued", "revision": revision}
        threading.Thread(target=self.build, args=(ident, flow, selection), daemon=True).start()
        return self.status(ident)

    def status(self, ident):
        with self.lock:
            if ident not in self.jobs:
                raise RecordError("Unknown report (report links last for this server session)")
            return dict(self.jobs[ident])

    def file(self, ident, kind):
        job = self.status(ident)
        if job["status"] != "ready" or kind not in {"pdf", "zip"}:
            raise RecordError("Report download is not ready")
        return self.store.home / "reports" / ident / ("report.pdf" if kind == "pdf" else "source.zip")

    def build(self, ident, flow, selection):
        folder = self.store.home / "reports" / ident
        try:
            with self.lock:
                self.jobs[ident]["status"] = "rendering"
            folder.mkdir(parents=True)
            (folder / "figures").mkdir()
            self.prepare(folder, flow, selection)
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
                for name in ["report.qmd", "_quarto.yml", "manifest.json", "snapshot.json", "report.pdf", *sorted(manifest["figures"])]:
                    bundle.write(folder / name, name)
            with self.lock:
                self.jobs[ident].update(status="ready", warnings=manifest["warnings"])
        except Exception as exc:
            message = str(exc) if isinstance(exc, RecordError) else "Report generation failed; check the local Quarto installation and available disk space."
            with self.lock:
                self.jobs[ident].update(status="failed", error=message)

    def prepare(self, folder, flow, selection):
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
        records = {key: flow["artifacts"][key] for key in ids if key in flow["artifacts"]}
        context = [{"id": key, "title": states[key]["title"]} for key in dict.fromkeys(p for a in actions for p in a.get("from", [])) if key not in selection and key in states]
        snapshot = clean({"project": flow["project"], "revision": flow["revision"], "selectedOrder": selection, "states": selected, "actions": actions, "artifacts": records, "omittedParentContext": context})
        manifest = {"schemaVersion": 1, "createdAt": now(), "projectRevision": flow["revision"], "selectedOrder": selection, "orderMeaning": "Presentation order only; no execution or dependency order inferred", "renderer": "Quarto with bundled Typst", "renderArgv": RENDER, "figures": [], "artifacts": {}, "warnings": [], "files": {}}
        body = ['---', 'title: ' + json.dumps(clean(flow["project"])), 'format:', '  typst:', '    papersize: a4', '    fontsize: 10pt', '    code-overflow: wrap', '    margin:', '      x: 20mm', '      y: 18mm', 'execute:', '  enabled: false', '---', '', 'Selected analysis · Revision ' + str(flow["revision"]), '', 'Selected presentation order; saved outputs, without rerunning analysis.', '']
        shown_scripts = {}
        total = 0
        for index, n in enumerate(selected, 1):
            body += ["# " + str(index) + ". " + txt(n["title"]), '']
            status = n.get("status")
            if status != "completed":
                body += [txt(status) + (' · not run' if status == 'planned' else ' · earlier execution not recorded' if status == 'imported' else ''), '']
            incoming = [a for a in actions if a["to"] == n["id"]]
            note = n.get("note") or ""
            if note:
                body += [txt(note), '']
            for action in incoming:
                parents = [states[p]["title"] + (" (outside selection)" if p not in selection else "") for p in action.get("from", []) if p in states]
                if parents:
                    body += ['Uses: ' + txt(', '.join(parents)), '']
                reason = action.get("reason")
                if reason and reason.strip() != note.strip():
                    body += [txt(reason), '']
                if action.get("annotation"):
                    body += ['Note: ' + txt(action['annotation']), '']
                scripts = action.get("code", {}).get("scriptArtifacts", [])
                for aid in scripts:
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
                        key = ar['sha256']
                        if key in shown_scripts:
                            body += [txt(ar['name']) + ' · shown in section ' + str(shown_scripts[key]), '']
                        else:
                            shown_scripts[key] = index
                            language = {'.py': 'python', '.r': 'r', '.sh': 'bash', '.js': 'javascript'}.get(Path(ar['name']).suffix.lower(), '')
                            body += [txt(ar['name']), ''] + code_cell(clean(source), language)
                    except (RecordError, OSError, UnicodeError) as exc:
                        warning = (ar['name'] if ar else aid) + ': ' + str(exc)
                        manifest['warnings'].append(clean(warning))
                        body += ['Script unavailable: ' + txt(warning), '']
                argv = action.get('argv') or action.get('argvTemplate') or []
                command = shlex.join(clean(argv)) if argv else clean(action.get('command') or '')
                if command:
                    if not scripts:
                        body += ['Script contents not recorded.', '']
                    body += code_cell(command, 'bash')
                if action.get('status') != 'completed' or action.get('exitCode') not in (None, 0):
                    body += [txt(action.get('status')) + ' · Exit ' + txt(str(action.get('exitCode', 'unknown'))), '']
                if action.get('error'):
                    body += ['Error: ' + txt(action['error']), '']
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
            if not figures and not tables and not note:
                body += ['No saved preview or summary is available.', '']
        body += ['Full record references and hashes are included in the accompanying source bundle. Preserved scripts are displayed as recorded text; file contents may contain original paths.', '']
        for name, data in {'_quarto.yml': 'project:\n  type: default\nexecute:\n  enabled: false\n', 'report.qmd': '\n'.join(body), 'snapshot.json': json.dumps(snapshot, indent=2) + '\n'}.items():
            (folder / name).write_text(data, encoding='utf-8')
            manifest['files'][name] = sha((folder / name).read_bytes())
        (folder / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        return manifest
