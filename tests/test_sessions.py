import json
import os
from pathlib import Path
import select
import shlex
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from saigen import sessions
from saigen.store import Store, RecordError, entity
from saigen.runner import run

REPO=Path(__file__).resolve().parent.parent

class SessionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.store=Store(self.root);self.store.init("Session checks")
        self.source=self.root/"source.txt";self.source.write_text("input\n")
        self.store.snapshot("Input",[self.source],ident="input")
        self.sid=sessions.begin(self.store,"Input",cwd=self.root)
    def command(self, text, status=0):
        sessions.command_start(self.store,self.sid,text,self.root)
        sessions.command_end(self.store,self.sid,status,[status])
    def test_commands_do_not_create_nodes_and_save_preserves_versions(self):
        original=len(self.store.flow()["states"])
        self.command("ls");self.command("false",1)
        self.assertEqual(len(self.store.flow()["states"]),original)
        out=self.root/"output.txt";out.write_text("first")
        first=sessions.save(self.store,self.sid,"First",[out],"Review result")
        self.assertEqual(first["status"],"saved")
        self.assertEqual([c["exitCode"] for c in first["terminal"]["commands"]],[0,1])
        self.assertEqual(self.store.flow()["actions"][-1]["from"],["input"])
        out.write_text("second");self.command("python analysis.py")
        second=sessions.save(self.store,self.sid,"Second",[out])
        self.assertEqual(len(second["terminal"]["commands"]),1)
        self.assertEqual(self.store.flow()["actions"][-1]["from"],[first["id"]])
        artifact=self.store.artifact(first["artifactIds"][0])
        self.assertEqual(self.store.artifact_path(artifact).read_text(),"first")
    def test_secret_redaction_and_pause_leave_no_command_content(self):
        self.command('tool --password "sensitive value"')
        self.command('export API_TOKEN=secret-value')
        sessions.pause(self.store,self.sid,True)
        self.command("echo totally-private-data")
        sessions.pause(self.store,self.sid,False)
        payload=json.dumps(self.store.events())
        for secret in ("sensitive value","secret-value","totally-private-data"):
            self.assertNotIn(secret,payload)
        commands=sessions.session(self.store.flow(),self.sid)["commands"]
        self.assertEqual(len(commands),2)
        self.assertTrue(all(c["redacted"] for c in commands))
        out=self.root/"out";out.write_text("data")
        saved=sessions.save(self.store,self.sid,"After pause",[out])
        self.assertEqual(len(saved["terminal"]["gaps"]),1)
    def test_missing_output_does_not_consume_commands(self):
        self.command("echo test")
        with self.assertRaises(OSError):sessions.save(self.store,self.sid,"Missing",[self.root/"missing"])
        self.assertEqual(sessions.session(self.store.flow(),self.sid)["cursor"],0)
        self.assertEqual(len(self.store.flow()["states"]),1)
    def test_closed_and_background_commands_do_not_imply_completed_work(self):
        self.command("sleep 2 &")
        sessions.command_start(self.store,self.sid,"exec something",self.root)
        sessions.close(self.store,self.sid,True)
        commands=sessions.session(self.store.flow(),self.sid)["commands"]
        self.assertTrue(commands[0]["backgroundPossible"])
        self.assertEqual(commands[0]["status"],"shell-returned")
        self.assertEqual(commands[1]["status"],"unknown")
    def test_run_and_save_share_session_without_duplicate_nodes(self):
        self.command("saigen run --from input --title Example -- tool")
        self.assertEqual(sessions.session(self.store.flow(),self.sid)["commands"],[])
        with patch.dict(os.environ,{"SAIGEN_SESSION":self.sid,"SAIGEN_PROJECT":str(self.root)}):
            result=run(self.store,["input"],"Wrapped",[sys.executable,"-c","print('ok')"])
        f=self.store.flow()
        self.assertEqual(len(f["actions"]),1)
        self.assertEqual(f["actions"][0]["sessionId"],self.sid)
        self.assertEqual(sessions.session(f,self.sid)["head"],result["state"])
    def test_concurrent_sessions_and_explicit_branch_keep_separate_commands(self):
        other=sessions.begin(self.store,"input")
        self.command("echo first")
        sessions.command_start(self.store,other,"echo second",self.root)
        sessions.command_end(self.store,other,0)
        out=self.root/"out";out.write_text("data")
        a=sessions.save(self.store,self.sid,"A",[out])
        b=sessions.save(self.store,other,"B",[out])
        self.assertEqual(self.store.flow()["actions"][-1]["from"],["input"])
        self.assertEqual(b["terminal"]["commands"][0]["command"],"echo second")
        with self.assertRaises(RecordError):
            self.store.edit([{"op":"edit_state","id":a["id"],"changes":{"terminal":{}}}],self.store.flow()["revision"])
    def test_first_save_in_empty_project_is_root_and_export_contains_activity(self):
        root=Store(self.root/"empty");root.init()
        sid=sessions.begin(root)
        sessions.command_start(root,sid,"echo data",self.root);sessions.command_end(root,sid,0)
        state=sessions.save(root,sid,"Starting result",[self.source])
        self.assertEqual(len(root.flow()["actions"]),0)
        self.assertEqual(len(state["terminal"]["commands"]),1)
        exported=self.root/"export.json";root.export(exported)
        self.assertIn(sid,json.loads(exported.read_text())["flow"]["sessions"])
    def test_saved_state_can_feed_wrapped_run(self):
        self.command("echo data")
        saved=sessions.save(self.store,self.sid,"Saved",[self.source])
        result=run(self.store,[saved["id"]],"From saved",[sys.executable,"-c","print('ok')"])
        self.assertEqual(result["status"],"completed")

@unittest.skipUnless(sys.platform=="darwin" or sys.platform.startswith("linux"),"Requires POSIX terminal")
class InteractiveShellTests(unittest.TestCase):
    def setUp(self):
        import pty
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.project=self.root/"project"
        self.zdot=self.root/"zsh";self.zdot.mkdir()
        self.rc='PROMPT="SAIGEN_TEST> "\nRPROMPT=""\nunsetopt ZLE\nprecmd() { return 0 }\nalias hello="print hello-alias"\n'
        (self.zdot/".zshrc").write_text(self.rc)
        env={k:v for k,v in os.environ.items() if not k.startswith("SAIGEN_")}
        env.update(ZDOTDIR=str(self.zdot),TERM="dumb",PYTHONPATH=str(REPO))
        self.master,slave=pty.openpty()
        self.proc=subprocess.Popen([sys.executable,"-B","-m","saigen","start","--project",str(self.project)]+(["--record-output"] if self._testMethodName=="test_optional_transcript_respects_pause" else []),
            cwd=self.root,env=env,stdin=slave,stdout=slave,stderr=slave,start_new_session=True)
        os.close(slave)
        self.addCleanup(self.close)
        self.wait_prompt()
        self.store=Store(self.project)
    def close(self):
        if self.proc.poll() is None:
            try:os.write(self.master,b"exit\n");self.proc.wait(timeout=3)
            except (OSError,subprocess.TimeoutExpired):
                self.proc.terminate()
                try:self.proc.wait(timeout=3)
                except subprocess.TimeoutExpired:self.proc.kill();self.proc.wait()
        os.close(self.master)
    def wait_prompt(self):
        output=b"";deadline=time.monotonic()+12
        while time.monotonic()<deadline:
            ready,_,_=select.select([self.master],[],[],.1)
            if ready:
                try:chunk=os.read(self.master,65536)
                except OSError:break
                if not chunk:break
                output+=chunk
                if output.endswith(b"SAIGEN_TEST> "):return output.decode(errors="replace")
            if self.proc.poll() is not None:break
        self.fail("Shell did not return a prompt: "+output.decode(errors="replace"))
    def command(self,text):
        os.write(self.master,text.encode()+b"\n")
        return self.wait_prompt()
    def session(self):
        return next(iter(self.store.flow()["sessions"].values()))
    def test_real_zsh_capture_save_pause_and_exit(self):
        self.command("hello")
        self.command("false")
        self.command("false | true")
        self.command("print '<svg xmlns=\"http://www.w3.org/2000/svg\"></svg>' > plot.svg")
        self.assertEqual(self.store.flow()["states"],[])
        output=self.command('saigen save --title "First result" --output plot.svg --reason "Inspect output"')
        self.assertNotIn('"error"',output)
        n=self.store.flow()["states"][0]
        self.assertEqual(len(n["terminal"]["commands"]),4)
        self.assertEqual(n["terminal"]["commands"][1]["exitCode"],1)
        self.assertEqual(n["terminal"]["commands"][2]["pipelineExitCodes"],[1,0])
        self.command("saigen pause")
        self.command("print do-not-record-this")
        self.command("saigen resume")
        self.command("print -- --token=private-token")
        self.assertNotIn("do-not-record-this",json.dumps(self.store.events()))
        self.assertNotIn("private-token",json.dumps(self.store.events()))
        self.command("print second > other.txt")
        self.command('saigen save --title Second --output other.txt')
        self.assertEqual(len(self.store.flow()["states"]),2)
        self.assertEqual((self.zdot/".zshrc").read_text(),self.rc)
        os.write(self.master,b"exit\n");self.proc.wait(timeout=5)
        self.assertEqual(self.session()["status"],"closed")
        self.assertFalse(list((self.project/".saigen"/"sessions").rglob("output.log")))
    def test_optional_transcript_respects_pause(self):
        self.command("print visible-output")
        self.command("saigen pause")
        self.command("print hidden-output")
        self.command("saigen resume")
        os.write(self.master,b"exit\n");self.proc.wait(timeout=5)
        s=self.session()
        log=self.store.artifact(s["logArtifacts"][0])
        output=self.store.artifact_path(log).read_text()
        self.assertIn("visible-output",output)
        self.assertNotIn("hidden-output",output)

    def test_multiline_and_relative_save_after_changing_directory(self):
        self.command("mkdir subdir")
        self.command("cd subdir")
        self.command("print 'two\nlines' > values.txt")
        self.command("saigen save --title Multiline --output values.txt")
        n=self.store.flow()["states"][0]
        self.assertIn("\n",n["terminal"]["commands"][-1]["command"])
        self.assertEqual(Path(n["terminal"]["commands"][-1]["cwd"]).name,"subdir")
        self.assertEqual(self.store.artifact_path(self.store.artifact(n["artifactIds"][0])).read_text(),"two\nlines\n")

    def test_interrupt_and_background_do_not_report_false_success(self):
        os.write(self.master,b"sleep 20\n")
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            if self.session()["commands"]:break
            time.sleep(.05)
        os.write(self.master,b"\x03")
        self.wait_prompt()
        cmd=self.session()["commands"][0]
        self.assertNotEqual(cmd["exitCode"],0)
        self.command("sleep 0.2 &")
        self.assertTrue(self.session()["commands"][-1]["backgroundPossible"])

if __name__=="__main__":unittest.main()
