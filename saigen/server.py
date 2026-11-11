"""Loopback-only viewer and edit API. The HTTP API never executes recorded analysis commands."""
from __future__ import annotations
import json
import mimetypes
from pathlib import Path
import secrets
import sysconfig
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from .store import Store, RecordError, Conflict
from .reports import Reports

WEB=Path(__file__).resolve().parent.parent/"web"
if not (WEB/"index.html").exists():WEB=Path(sysconfig.get_path("data"))/"share"/"saigenbio"/"web"
class Server(ThreadingHTTPServer):
    daemon_threads=True
    def __init__(self, address, store):
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
            if path=="/api/flow": return self.reply(200,self.store.flow())
            if path=="/api/revision": return self.reply(200,{"revision":self.store.flow()["revision"]})
            if path=="/api/session": return self.reply(200,{"token":self.server.token,"projectRoot":str(self.store.root)})
            if path=="/api/history":
                events=self.store.events()
                for event in events: event.pop("inverse",None)
                return self.reply(200,events)
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
            routes={"/":"index.html","/app.js":"app.js","/style.css":"style.css"}
            if path in routes:
                name=routes[path]
                mime={"index.html":"text/html; charset=utf-8","app.js":"text/javascript; charset=utf-8","style.css":"text/css; charset=utf-8"}[name]
                return self.reply(200,(WEB/name).read_bytes(),mime,{"Content-Security-Policy":"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'"})
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
            if path=="/api/reports": return self.reply(202,self.server.reports.start(body.get("selected"),body["revision"]))
            if path=="/api/edit": flow=self.store.edit(body.get("operations"),body["revision"])
            elif path=="/api/undo": flow=self.store.undo(body.get("event"),body["revision"])
            else: return self.reply(404,{"error":"Not found"})
            self.reply(200,flow)
        except Conflict as exc: self.reply(409,{"error":str(exc)})
        except (RecordError,ValueError,TypeError,KeyError) as exc: self.reply(400,{"error":str(exc)})

def serve(store,port=8765):
    store.flow()
    with Server(("127.0.0.1",port),store) as server:
        print(f"SaigenBio: http://127.0.0.1:{server.server_port}",flush=True)
        try: server.serve_forever()
        except KeyboardInterrupt: pass
