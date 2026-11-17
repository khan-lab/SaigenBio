"""Loopback-only viewer and edit API. The HTTP API never executes recorded analysis commands."""
from __future__ import annotations
import json
from pathlib import Path
import secrets
import sysconfig
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from .records import RecordError, Conflict
from .reports import Reports
from .workflows.service import WorkflowService
from .views import CanvasView

UI=Path(__file__).resolve().parent.parent/"ui"
if not (UI/"index.html").exists():UI=Path(sysconfig.get_path("data"))/"share"/"saigenbio"/"ui"
class Server(ThreadingHTTPServer):
    daemon_threads=True
    def __init__(self, address, store):
        self.canvas=CanvasView(store)
        self.store=store
        self.reports=Reports(store)
        self.token=secrets.token_urlsafe(32)
        self.stop_event=threading.Event()
        super().__init__(address,Handler)
        self.recovery=threading.Thread(target=self.recover,daemon=True)
        self.recovery.start()
    def recover(self):
        while not self.stop_event.wait(5):
            try: self.store.recover()
            except Exception: pass
    def server_close(self):
        self.stop_event.set()
        super().server_close()
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    @property
    def store(self): return self.server.store
    def reply(self,status,data,mime="application/json",extra=None):
        if not isinstance(data,bytes):
            data=(json.dumps(data) if mime=="application/json" else str(data)).encode()
        self.send_response(status)
        self.send_header("Content-Type",mime)
        self.send_header("Content-Length",str(len(data)))
        self.send_header("Cache-Control","no-store")
        self.send_header("X-Content-Type-Options","nosniff")
        self.send_header("Referrer-Policy","no-referrer")
        self.send_header("X-Frame-Options","DENY")
        if extra:
            for key,value in extra.items(): self.send_header(key,value)
        self.end_headers()
        try: self.wfile.write(data)
        except (BrokenPipeError,ConnectionResetError): pass
    def host_ok(self):
        return self.headers.get("Host") in {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
    def do_GET(self):
        if not self.host_ok(): return self.reply(403,{"error":"Invalid host"})
        path=urlsplit(self.path).path
        try:
            if path.startswith("/api/reports/"):
                origin=self.headers.get("Origin")
                allowed={f"http://127.0.0.1:{self.server.server_port}",f"http://localhost:{self.server.server_port}"}
                if (origin and origin not in allowed) or not secrets.compare_digest(self.headers.get("X-Saigen-Token",""),self.server.token):
                    return self.reply(403,{"error":"Invalid report session"})
                parts=path.split("/")
                if len(parts)==4: return self.reply(200,self.server.reports.status(parts[3]))
                if len(parts)==5 and parts[4] in {"pdf","zip"}:
                    source=self.server.reports.file(parts[3],parts[4])
                    return self.reply(200,source.read_bytes(),"application/pdf" if parts[4]=="pdf" else "application/zip",{"Content-Disposition":f'attachment; filename="saigen-report.{parts[4]}"',"Content-Security-Policy":"sandbox; default-src 'none'"})
                return self.reply(404,{"error":"Not found"})
            if path=="/api/flow":
                return self.reply(200,self.server.canvas.flow())
            if path=="/api/revision": return self.reply(200,{"revision":self.store.flow()["revision"]})
            if path=="/api/session": return self.reply(200,{"token":self.server.token,"projectRoot":str(self.store.root)})
            if path=="/api/history":
                return self.reply(200,self.server.canvas.history())
            if path.startswith("/api/story/"):
                from .story import read
                return self.reply(200,read(self.store,path.removeprefix("/api/story/")))
            if path=="/api/archive":
                from .story import archive_index
                return self.reply(200,archive_index(self.store))
            if path.startswith("/api/artifacts/"):
                ident=path.removeprefix("/api/artifacts/")
                artifact=self.store.artifact(ident)
                source=self.store.artifact_path(artifact)
                # Only preserved, registered files are previewed; no arbitrary path API.
                if artifact["storage"]!="preserved":
                    return self.reply(409,{"error":"External reference verified, but preview is unavailable. Preserve a copy to preview it."})
                if artifact["size"]>10*1024*1024:
                    return self.reply(413,{"error":"Preview limited to 10 MB; use the recorded file path for larger files."})
                mime=artifact["mime"]
                if mime not in {"image/svg+xml","image/png","image/jpeg","image/webp","image/gif"}:
                    mime="text/plain; charset=utf-8"
                return self.reply(200,source.read_bytes(),mime,{"Content-Security-Policy":"sandbox; default-src 'none'; style-src 'unsafe-inline'"})
            routes={"/reconstruction.js":"reconstruction.js","/verification.js":"verification.js","/story.js":"story.js","/details.js":"details.js","/":"index.html","/app.js":"app.js","/geometry.js":"geometry.js","/paths.js":"paths.js","/api.js":"api.js","/reports.js":"reports.js","/workflows.js":"workflows.js","/style.css":"style.css"}
            assets={"logo.svg":"image/svg+xml","logo-512.png":"image/png","logo-1024.png":"image/png","favicon.svg":"image/svg+xml","favicon-16.png":"image/png","favicon-32.png":"image/png","favicon-48.png":"image/png","favicon.ico":"image/vnd.microsoft.icon"}
            routes.update({"/assets/"+name:"assets/"+name for name in assets})
            routes["/favicon.ico"]="assets/favicon.ico"
            if path in routes:
                name=routes[path]
                mime={"reconstruction.js":"text/javascript; charset=utf-8","verification.js":"text/javascript; charset=utf-8","story.js":"text/javascript; charset=utf-8","details.js":"text/javascript; charset=utf-8","workflows.js":"text/javascript; charset=utf-8","api.js":"text/javascript; charset=utf-8","reports.js":"text/javascript; charset=utf-8","geometry.js":"text/javascript; charset=utf-8","paths.js":"text/javascript; charset=utf-8","index.html":"text/html; charset=utf-8","app.js":"text/javascript; charset=utf-8","style.css":"text/css; charset=utf-8"}.get(name,assets.get(Path(name).name))
                return self.reply(200,(UI/name).read_bytes(),mime,{"Content-Security-Policy":"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'"})
            self.reply(404,{"error":"Not found"})
        except (RecordError,OSError) as exc: self.reply(409,{"error":str(exc)})
    def do_POST(self):
        if not self.host_ok(): return self.reply(403,{"error":"Invalid host"})
        origin=self.headers.get("Origin")
        allowed={f"http://127.0.0.1:{self.server.server_port}",f"http://localhost:{self.server.server_port}"}
        if origin and origin not in allowed: return self.reply(403,{"error":"Invalid origin"})
        if not secrets.compare_digest(self.headers.get("X-Saigen-Token",""),self.server.token):
            return self.reply(403,{"error":"Invalid session"})
        if self.headers.get_content_type()!="application/json":
            return self.reply(415,{"error":"Expected JSON"})
        try:
            length=int(self.headers.get("Content-Length","0"))
            if not 0<length<=1024*1024: return self.reply(413,{"error":"Invalid request size"})
            body=json.loads(self.rfile.read(length))
            if not isinstance(body,dict) or type(body.get("revision")) is not int: raise RecordError("A project revision is required")
            path=urlsplit(self.path).path
            if path=="/api/explanations":
                from .story import append
                flow=append(self.store,body.get("entry"),body["revision"],"Human")
                return self.reply(200,self.server.canvas.with_removal_options(flow))
            if path.startswith("/api/verifications/") and path.endswith("/approve") and len(path.split("/"))==5:
                from .verification import approve
                flow=approve(self.store,path.split("/")[3],body.get("digest"),body["revision"],"Human")
                return self.reply(200,self.server.canvas.with_removal_options(flow))
            if path=="/api/reports":
                options={"template":body["template"]} if "template" in body else {}
                return self.reply(202,self.server.reports.start(body.get("selected"),body["revision"],**options))
            if path=="/api/reports/preview":
                return self.reply(200,self.server.reports.preview(body.get("selected"),body["revision"],body.get("template","analysis-notebook")))
            if path.startswith("/api/reports/") and path.endswith("/render") and len(path.split("/"))==5:
                return self.reply(202,self.server.reports.render_preview(path.split("/")[3],body["revision"]))
            if path.startswith("/api/reconstructions/") and len(path.split("/"))==5:
                from .reconstruction import review
                review(self.store,path.split("/")[3],path.split("/")[4],body["revision"],"Human",state_id=body.get("stateId"),connection_id=body.get("connectionId"),evidence_id=body.get("evidenceId"),reason=body.get("reason",""))
                flow=self.store.flow()
            elif path=="/api/edit": flow=self.store.edit(body.get("operations"),body["revision"])
            elif path.startswith("/api/workflows/") and path.endswith("/cancel") and len(path.split("/")) == 5:
                WorkflowService(self.store).cancel(path.split("/")[3], revision=body["revision"], reason=body.get("reason"), actor="Human")
                flow=self.store.flow()
            elif path=="/api/undo": flow=self.store.undo(body.get("event"),body["revision"])
            else: return self.reply(404,{"error":"Not found"})
            self.reply(200,self.server.canvas.with_removal_options(flow))
        except Conflict as exc: self.reply(409,{"error":str(exc)})
        except (RecordError,ValueError,TypeError,KeyError) as exc: self.reply(400,{"error":str(exc)})

def serve(store,port=8767):
    store.flow()
    with Server(("127.0.0.1",port),store) as server:
        print(f"SaigenBio: http://127.0.0.1:{server.server_port}",flush=True)
        try: server.serve_forever()
        except KeyboardInterrupt: pass
