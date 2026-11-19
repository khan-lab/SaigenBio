import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
import urllib.error
from saigen.store import Store, RecordError, Conflict, entity
from saigen.runner import run
from saigen.server import Server

REPO=Path(__file__).resolve().parent.parent
class RecorderTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.store=Store(self.root);self.store.init("Test")
        self.input=self.root/"input.txt";self.input.write_text("original\n")
        self.parent=self.store.snapshot("Input",[self.input],ident="input")
    def execute(self,code,outputs=(),**kw):
        return run(self.store,["input"],"Attempt",[sys.executable,"-c",code],outputs=outputs,**kw)
    def test_method_explanation_and_preserved_excerpt(self):
        script=self.root/"method.py"
        script.write_text("# purpose\nvalue = 5\nprint(value)\n")
        result=self.execute("pass",explanation="Apply the depth threshold",scripts=["method.py"],script_excerpts=["method.py:2:3"])
        action=next(a for a in self.store.flow()["actions"] if a["to"]==result["state"])
        self.assertEqual(len(action["code"]["scriptArtifacts"]),1)
        explanation=action["code"]["explanation"]
        self.assertEqual(explanation["summary"],"Apply the depth threshold")
        self.assertEqual(explanation["recordedBy"],"AI agent")
        excerpt=explanation["excerpts"][0]
        self.assertEqual(excerpt["text"],"value = 5\nprint(value)")
        script.write_text("changed")
        artifact=self.store.artifact(excerpt["artifactId"])
        self.assertIn(excerpt["text"],self.store.artifact_path(artifact).read_text())

    def test_invalid_excerpt_never_starts_command(self):
        script=self.root/"method.py";script.write_text("pass\n")
        for selection in ("method.py:0:1","method.py:1:2","method.py:1:41","malformed"):
            with self.subTest(selection=selection), self.assertRaises(RecordError):
                self.execute("raise Exception('must not run')",script_excerpts=[selection])
        self.assertEqual(self.store.flow()["actions"],[])

    def test_root_acquisition_preserves_provenance_and_preview(self):
        result=run(self.store,[],"Dataset",[sys.executable,"-c",
            "import pathlib;pathlib.Path('samples.tsv').write_text('sample\\tgeneration\\nA\\t5000\\n')"],
            acquisition=True,source_urls=["https://example.org/data"],outputs=["samples.tsv"],
            expected="Expected: downloaded sample metadata")
        self.assertEqual(result["status"],"completed")
        f=self.store.flow()
        action=entity(f,"actions",result["action"])
        self.assertEqual(action["from"],[])
        self.assertTrue(action["acquisition"])
        self.assertEqual(action["environment"]["declaredSourceURLs"],["https://example.org/data"])
        state=entity(f,"states",result["state"])
        art=f["artifacts"][state["artifactIds"][0]]
        self.assertEqual(art["tablePreview"]["columns"],["sample","generation"])
        self.assertEqual(art["tablePreview"]["rows"],[["A","5000"]])
        self.assertEqual(self.store.artifact_path(art).read_text(),"sample\tgeneration\nA\t5000\n")

    def test_table_preview_is_bounded_and_reference_not_previewed(self):
        p=self.root/"wide.csv"
        p.write_text("a,b,c,d,e,f,g\n"+("x"*300+",2,3,4,5,6,7\n")*20)
        a=self.store.capture(p)
        self.assertEqual(len(a["tablePreview"]["columns"]),6)
        self.assertEqual(len(a["tablePreview"]["rows"]),5)
        self.assertEqual(len(a["tablePreview"]["rows"][0][0]),160)
        self.assertIsNone(self.store.capture(p,preserve=False)["tablePreview"])

    def test_plan_chain_and_execution_lifecycle(self):
        a=self.store.plan("First",["input"],"A first table.",["out.txt"],ident="first",
                          details="Count input rows.",requires="Review inputs first.")
        self.store.plan("Second",["first"],"Expected: figure",ident="second")
        self.assertEqual(self.store.flow()["actions"],[])
        self.assertGreater(entity(self.store.flow(),"states","second")["x"],a["x"])
        with self.assertRaises(RecordError):
            run(self.store,["first"],"Second",[sys.executable,"-c","pass"],planned="second")
        seen=[]
        def observe():
            for _ in range(100):
                f=self.store.flow()
                if f["actions"]:
                    seen.append(f)
                    return
                time.sleep(.01)
        t=threading.Thread(target=observe);t.start()
        result=run(self.store,["input"],"First",[sys.executable,"-c",
            "import time,pathlib;time.sleep(.2);pathlib.Path('out.txt').write_text('ok')"],
            outputs=["out.txt"],planned="first")
        t.join()
        self.assertEqual(seen[0]["actions"][0]["status"],"running")
        self.assertEqual(entity(seen[0],"states","first")["status"],"running")
        f=self.store.flow()
        self.assertEqual(len(f["states"]),3)
        self.assertEqual(entity(f,"states","first")["status"],"completed")
        self.assertEqual(entity(f,"states","first")["x"],a["x"])
        original=entity(f,"states","first")["plan"]
        for key in ("expectedSummary","planDetails","planRequires","expectedFiles","planParents"):
            self.assertEqual(original[key],a[key])
        self.assertEqual(entity(f,"states","second")["status"],"planned")
        self.assertEqual(len(f["actions"]),1)
        result=run(self.store,["first"],"Second",[sys.executable,"-c","pass"],planned="second")
        self.assertEqual(result["state"],"second")
        self.assertEqual(len(self.store.flow()["actions"]),2)
        with self.assertRaises(RecordError):
            run(self.store,["input"],"First",[sys.executable,"-c","pass"],planned="first")

    def test_legacy_plan_retains_text_when_executed(self):
        self.store.plan("Legacy",["input"],"Expected: old explanation",ident="legacy")
        def legacy(f):
            n=entity(f,"states","legacy")
            n.pop("planDetails");n.pop("planRequires")
            n["note"]=n["expectedSummary"]
            return {},None
        self.store.update("test.legacy","Test",legacy)
        run(self.store,["input"],"Legacy",[sys.executable,"-c","pass"],planned="legacy")
        p=entity(self.store.flow(),"states","legacy")["plan"]
        self.assertEqual(p["note"],"Expected: old explanation")
        self.assertNotIn("planDetails",p)

    def test_plan_cli_separates_fields_without_execution(self):
        result=subprocess.run([sys.executable,"-B","-m","saigen","plan","--project",str(self.root),
            "--from","input","--id","qc","--title","Spatial QC summary",
            "--expect","QC plots and sample counts.","--details","Inspect coverage.",
            "--requires","Review QC before normalization.","--output","qc.svg"],
            cwd=REPO,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        n=json.loads(result.stdout)
        self.assertEqual(n["expectedSummary"],"QC plots and sample counts.")
        self.assertEqual(n["planDetails"],"Inspect coverage.")
        self.assertEqual(n["planRequires"],"Review QC before normalization.")
        self.assertEqual(n["note"],"")
        self.assertEqual(self.store.flow()["actions"],[])

    def test_manual_plan_fields_can_be_edited_and_undone(self):
        f=self.store.edit([{"op":"add_state","id":"manual","value":{
            "title":"QC summary","expectedSummary":"QC plots.","planDetails":"Inspect counts.",
            "planRequires":"Review inputs."}}],self.store.flow()["revision"])
        f=self.store.edit([{"op":"edit_state","id":"manual","changes":{
            "planRequires":"Review metadata."}}],f["revision"])
        self.assertEqual(entity(f,"states","manual")["planRequires"],"Review metadata.")
        self.store.undo(f["revision"],f["revision"])
        self.assertEqual(entity(self.store.flow(),"states","manual")["planRequires"],"Review inputs.")

    def test_preserved_inputs_outputs_and_reopen(self):
        result=run(self.store,["input"],"Copy",[sys.executable,"-c","import pathlib,sys;pathlib.Path('out.txt').write_text(pathlib.Path(sys.argv[1]).read_text())","{input:0}"],inputs=[str(self.input)],outputs=["out.txt"],reason="Test copying")
        self.assertEqual(result["status"],"completed")
        flow=Store(self.root).flow();n=entity(flow,"states",result["state"])
        art=flow["artifacts"][n["artifactIds"][0]]
        (Path(result["workdir"])/"out.txt").write_text("changed")
        self.input.write_text("changed input")
        self.assertEqual(self.store.artifact_path(art).read_text(),"original\n")
        self.assertEqual(len(n["manifest"]),2)
        a=entity(flow,"actions",result["action"])
        self.assertEqual(a["exitCode"],0);self.assertTrue(a["startedAt"]<=a["finishedAt"])
        self.assertEqual(a["reason"],"Test copying")
    def test_failure_and_retry_are_separate(self):
        failed=self.execute("import sys;print('bad',file=sys.stderr);sys.exit(3)")
        good=self.execute("print('ok')")
        self.assertEqual(failed["status"],"failed");self.assertEqual(good["status"],"completed")
        self.assertNotEqual(failed["state"],good["state"])
        flow=self.store.flow()
        self.assertEqual(entity(flow,"actions",failed["action"])["exitCode"],3)
        self.assertEqual(len(flow["states"]),3)
    def test_missing_output_is_failure_even_with_zero_exit(self):
        result=self.execute("print('finished')",["missing.svg"])
        self.assertEqual(result["exitCode"],0);self.assertEqual(result["status"],"failed")
        self.assertIn("missing.svg",result["error"])
    def test_invalid_input_placeholder_does_not_start_a_run(self):
        revision=self.store.flow()["revision"]
        with self.assertRaises(RecordError):
            run(self.store,["input"],"Bad",[sys.executable,"{input:9}"])
        self.assertEqual(self.store.flow()["revision"],revision)
    def test_stdout_can_be_a_preserved_output(self):
        result=self.execute("print('content')",stdout_name="data/result.txt")
        n=entity(self.store.flow(),"states",result["state"])
        self.assertEqual(n["files"],["data/result.txt"])
    def test_group_layout_edit_and_undo_preserve_execution_evidence(self):
        result=self.execute("print('synthetic layout fixture')")
        before=self.store.flow()
        ids=["input",result["state"]]
        positions={n["id"]:(n["x"],n["y"]) for n in before["states"]}
        ops=[{"op":"edit_state","id":sid,"changes":{
            "x":positions[sid][0]+70,"y":positions[sid][1]+45}} for sid in ids]
        moved=self.store.edit(ops,before["revision"])
        self.assertEqual(moved["revision"],before["revision"]+1)
        self.assertEqual(moved["actions"],before["actions"])
        self.assertEqual(moved["artifacts"],before["artifacts"])
        for old,new in zip(before["states"],moved["states"]):
            for key in ("status","origin","artifactIds","manifest","writtenBy","performedBy"):
                self.assertEqual(new.get(key),old.get(key))
        self.store.undo(moved["revision"],moved["revision"])
        restored=self.store.flow()
        self.assertEqual({n["id"]:(n["x"],n["y"]) for n in restored["states"]},positions)
        self.assertEqual(restored["actions"],before["actions"])
        self.assertEqual(restored["artifacts"],before["artifacts"])

    def test_stale_edit_rejected_and_execution_identity_preserved(self):
        rev=self.store.flow()["revision"]
        flow=self.store.edit([{"op":"edit_state","id":"input","changes":{"note":"Human note"}}],rev)
        with self.assertRaises(Conflict):
            self.store.edit([{"op":"edit_state","id":"input","changes":{"note":"stale"}}],rev)
        n=entity(self.store.flow(),"states","input")
        self.assertEqual(n["writtenBy"],"AI agent");self.assertEqual(n["lastEditedBy"],"Human")
        self.store.undo(flow["revision"],flow["revision"])
        self.assertEqual(entity(self.store.flow(),"states","input")["note"],"")
        self.assertEqual(self.store.events()[-1]["kind"],"flow.undo")
    def test_executed_command_and_imported_state_cannot_be_rewritten(self):
        result=self.execute("print('ok')")
        with self.assertRaises(RecordError):
            self.store.edit([{"op":"edit_action","id":result["action"],"changes":{"command":"fake"}}],self.store.flow()["revision"])
        with self.assertRaises(RecordError):
            self.store.edit([{"op":"delete_state","id":"input"}],self.store.flow()["revision"])
    def test_atomic_cycle_rejection(self):
        rev=self.store.flow()["revision"]
        ops=[{"op":"add_state","id":i,"value":{"title":i}} for i in ("a","b")]
        ops += [{"op":"add_action","id":"ab","value":{"from":["a"],"to":"b","label":"ab"}},{"op":"add_action","id":"ba","value":{"from":["b"],"to":"a","label":"ba"}}]
        with self.assertRaises(RecordError): self.store.edit(ops,rev)
        self.assertEqual(self.store.flow()["revision"],rev)
        self.assertEqual(len(self.store.flow()["states"]),1)
    def test_large_position_batch_saves_and_undoes_atomically(self):
        ids = [f"node{i}" for i in range(100)]
        before = self.store.edit(
            [{"op":"add_state","id":ident,"value":{"title":ident}} for ident in ids],
            self.store.flow()["revision"],
        )
        positions = {n["id"]: (n["x"], n["y"]) for n in before["states"]}
        moves = [{"op":"edit_state","id":ident,"changes":{"x":64,"y":index*204}}
                 for index, ident in enumerate(positions)]
        with self.assertRaises(RecordError):
            self.store.edit(moves[:-1] + [moves[0]], before["revision"])
        with self.assertRaises(RecordError):
            self.store.edit(moves[:-1] + [{**moves[-1], "changes":{"note":"not a move"}}],
                            before["revision"])
        self.assertEqual(self.store.flow()["revision"], before["revision"])
        after = self.store.edit(moves, before["revision"])
        self.assertEqual(after["revision"], before["revision"] + 1)
        self.assertTrue(all(n["x"] == 64 for n in after["states"]))
        restored = self.store.undo(after["revision"], after["revision"])
        self.assertEqual({n["id"]: (n["x"], n["y"]) for n in restored["states"]}, positions)

    def test_multiple_undo_preserves_history(self):
        f=self.store.edit([{"op":"add_state","id":"plan","value":{"title":"Plan"}}],self.store.flow()["revision"])
        creation=f["revision"]
        f=self.store.edit([{"op":"edit_state","id":"plan","changes":{"x":320,"title":"New title"}}],f["revision"])
        change=f["revision"]
        f=self.store.undo(change,f["revision"])
        f=self.store.undo(creation,f["revision"])
        self.assertEqual(len(f["states"]),1)
        self.assertEqual([e["kind"] for e in self.store.events()].count("flow.undo"),2)
    def test_concurrent_edits_have_one_winner(self):
        rev=self.store.flow()["revision"];results=[]
        def edit(value):
            try:self.store.edit([{"op":"edit_state","id":"input","changes":{"note":value}}],rev);results.append("saved")
            except Conflict: results.append("conflict")
        threads=[threading.Thread(target=edit,args=(str(i),)) for i in range(2)]
        for t in threads:t.start()
        for t in threads:t.join()
        self.assertCountEqual(results,["saved","conflict"])
    def test_external_file_change_is_detected(self):
        a=self.store.capture(self.input,preserve=False)
        self.input.write_text("different")
        with self.assertRaisesRegex(RecordError,"changed"):self.store.artifact_path(a)
    def test_lost_heartbeat_becomes_unknown_then_can_finish(self):
        aid,sid=self.store.begin("Lost",["input"],["program"],"AI agent","test",[],[],{}, {})
        self.store.recover(seconds=-1)
        self.assertEqual(entity(self.store.flow(),"states",sid)["status"],"unknown")
        self.store.finish(aid,"completed",0,[],[])
        self.assertEqual(entity(self.store.flow(),"states",sid)["status"],"completed")
    def test_cancellation_is_recorded(self):
        p=subprocess.Popen([sys.executable,"-B","-m","saigen","--project",str(self.root),"run","--from","input","--title","Long task","--",sys.executable,"-c","import time;time.sleep(20)"],cwd=REPO,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            deadline=time.monotonic()+8
            while time.monotonic()<deadline:
                if self.store.flow()["actions"]:break
                time.sleep(.05)
            self.assertTrue(self.store.flow()["actions"])
            time.sleep(.2);p.send_signal(signal.SIGTERM)
            stdout,stderr=p.communicate(timeout=8)
            self.assertEqual(p.returncode,130,(stdout,stderr))
            self.assertEqual(self.store.flow()["actions"][0]["status"],"cancelled")
        finally:
            if p.poll() is None:p.kill();p.wait()
    def test_export_contains_the_same_revision_and_history(self):
        path=self.root/"history.json";self.store.export(path)
        data=json.loads(path.read_text())
        self.assertEqual(data["flow"]["revision"],data["events"][-1]["revision"])

class ServerTests(unittest.TestCase):
    def setUp(self):
        RecorderTests.setUp(self)
        self.server=Server(("127.0.0.1",0),self.store)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.base=f"http://127.0.0.1:{self.server.server_port}"
        self.addCleanup(self.close)
    def close(self):
        self.server.shutdown();self.server.server_close();self.thread.join()
    def get(self,path):
        return urllib.request.urlopen(self.base+path)
    def test_http_artifacts_and_token_protected_edits(self):
        with self.get("/api/session") as r: token=json.load(r)["token"]
        body={"revision":self.store.flow()["revision"],"operations":[{"op":"edit_state","id":"input","changes":{"note":"via API"}}]}
        req=urllib.request.Request(self.base+"/api/edit",data=json.dumps(body).encode(),headers={"Content-Type":"application/json"})
        with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(req)
        self.assertEqual(e.exception.code,403)
        req.add_header("X-Saigen-Token",token)
        with urllib.request.urlopen(req) as r:self.assertEqual(json.load(r)["states"][0]["note"],"via API")
        ident=self.parent["artifactIds"][0]
        with self.get("/api/artifacts/"+ident) as r:
            self.assertEqual(r.read(),b"original\n")
            self.assertIn("sandbox",r.headers["Content-Security-Policy"])
        with self.assertRaises(urllib.error.HTTPError):self.get("/api/artifacts/../../etc/passwd")

if __name__=="__main__": unittest.main()
