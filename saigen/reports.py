"""Selected-state reports. Recorded text is data; only Quarto/Typst is executed."""
from __future__ import annotations
import hashlib
import json
import re
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
        body = ['---', 'title: "Selected analysis states"', 'format:', '  typst:', '    papersize: a4', '    fontsize: 10pt', '    margin:', '      x: 20mm', '      y: 18mm', 'execute:', '  enabled: false', '---', '', txt(flow["project"]) + " · Revision " + str(flow["revision"]), '', 'Selection order is presentation order. Omitted states are excluded; named parents provide context only. Saved evidence is reused without running analyses. Recorded reasons are declarations, not new conclusions.', '']
        total = 0
        for index, n in enumerate(selected, 1):
            if index > 1: body += ["{{< pagebreak >}}", ""]
            body += ["# " + str(index) + ". " + txt(n["title"]), '', 'Status: ' + txt(n.get("status")) + ' · Origin: ' + txt(n.get("origin")), '']
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
                    figures += ['![' + txt(ar["name"]) + '](' + name + '){width=100%}', '', 'Preserved figure · ' + txt(ar["name"]) + ' · SHA-256 ' + ar["sha256"][:16], '']
                except (RecordError, OSError, ElementTree.ParseError) as exc:
                    warning = clean(ar["name"]) + ": " + str(exc)
                    manifest["warnings"].append(warning)
                    figures += ['Figure unavailable: ' + literal(warning), '']
            body += figures
            if not figures:
                body += ['No supported preserved figure is available for this state. ' + ('This is a plan; no execution is established.' if n.get('status') == 'planned' else 'Use the recorded notes and action status below; no conclusion is inferred.'), '']
            body += ['Recorded state note: ' + txt(n.get("note") or "Not recorded"), '']
            for a in [a for a in actions if a["to"] == n["id"]]:
                parents = ", ".join(states[p]["title"] + (" (omitted context)" if p not in selection else "") for p in a.get("from", []) if p in states)
                body += ['## Recorded action: ' + txt(a.get("label")), '', 'From: ' + txt(parents), '', 'Status: ' + txt(a.get("status")) + ' · Exit: ' + txt(str(a["exitCode"]) if a.get("exitCode") is not None else "unknown"), '', 'Stated reason: ' + txt(a.get("reason") or "Not recorded"), '']
                if a.get("annotation"):
                    body += ['Human note: ' + txt(a["annotation"]), '']
                command = " ".join(a.get("argv") or a.get("argvTemplate") or []) or a.get("command")
                body += ['Command / options (recorded text):', '', txt(command or 'Not recorded'), '']
                if a.get('error'):
                    body += ['Recorded error: ' + txt(a['error']), '']
            for c in (n.get('terminal') or {}).get('commands', []):
                body += ['Recorded terminal command (' + txt(c.get('status')) + '): ' + txt(c.get('command')), '']
            if not figures:
                body += ['Provenance: recorded by ' + txt(n.get('writtenBy')) + ' · Code revision: ' + txt(n.get('codeRef') or 'Not recorded') + '. Imports do not establish upstream execution; shell groupings do not establish file dependencies.', '']
        body += ['{{< pagebreak >}}', '', '# Compact provenance', '', 'Editable source, selected records, verified figures, full source references and full SHA-256 hashes accompany this PDF in the source bundle. Hashes below are abbreviated. Original absolute paths are aliased; embedded labels inside preserved figures are unchanged. Re-render with: quarto render report.qmd --to typst --output report.pdf --no-execute', '']
        for n in selected:
            body += [txt(n['id']) + ': ' + txt(n['title']) + ' · Code: ' + txt(n.get('codeRef') or 'Not recorded'), '']
        for aid, ar in sorted(records.items()):
            body += [txt(aid) + ' · ' + txt(ar['name']) + ' · SHA-256 ' + ar['sha256'][:16] + '…', '']
        for warning in manifest['warnings']:
            body += ['Warning: ' + literal(warning), '']
        for name, data in {'_quarto.yml': 'project:\n  type: default\nexecute:\n  enabled: false\n', 'report.qmd': '\n'.join(body), 'snapshot.json': json.dumps(snapshot, indent=2) + '\n'}.items():
            (folder / name).write_text(data, encoding='utf-8')
            manifest['files'][name] = sha((folder / name).read_bytes())
        (folder / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        return manifest
