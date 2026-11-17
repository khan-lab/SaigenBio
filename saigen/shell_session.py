"""A scoped interactive zsh, with optional output-only PTY recording."""
from __future__ import annotations
import errno
import fcntl
import os
from pathlib import Path
import pty
import select
import shlex
import shutil
import signal
import sys
import tempfile
import termios
import tty
import time
from .records import RecordError
from . import sessions

def _forward(store, ident, argv, env, output_path=None):
    """Forward terminal bytes, logging only output when explicitly requested."""
    pid,master=pty.fork()
    if pid==0:
        try:os.execvpe(argv[0],argv,env)
        except OSError:
            os.write(2,b"SaigenBio: could not launch zsh.\n")
            os._exit(127)
    fd=sys.stdin.fileno()
    previous=termios.tcgetattr(fd)
    transcript=None
    old_winch=signal.getsignal(signal.SIGWINCH)
    old_term=signal.getsignal(signal.SIGTERM)
    child_status=None
    def terminated(*_):raise KeyboardInterrupt
    def resize(*_):
        try:fcntl.ioctl(master,termios.TIOCSWINSZ,fcntl.ioctl(fd,termios.TIOCGWINSZ,b"\0"*8))
        except OSError:pass
    resize()
    signal.signal(signal.SIGWINCH,resize)
    signal.signal(signal.SIGTERM,terminated)
    try:
        if output_path:
            transcript=open(output_path,"wb")
            os.chmod(output_path,0o600)
        tty.setraw(fd)
        while True:
            readers,_,_=select.select([fd,master],[],[],.1)
            if master in readers:
                try:data=os.read(master,65536)
                except OSError as exc:
                    if exc.errno==errno.EIO:break
                    raise
                if not data:break
                sys.stdout.buffer.write(data);sys.stdout.buffer.flush()
                if transcript:
                    try:paused=sessions.session(store.flow(),ident)["paused"]
                    except Exception:paused=True
                    if not paused:transcript.write(data);transcript.flush()
            if fd in readers:
                data=os.read(fd,65536)
                if not data:break
                offset=0
                while offset<len(data):offset+=os.write(master,data[offset:])
            ended,status=os.waitpid(pid,os.WNOHANG)
            if ended:
                child_status=status
                break
    finally:
        termios.tcsetattr(fd,termios.TCSANOW,previous)
        signal.signal(signal.SIGWINCH,old_winch)
        signal.signal(signal.SIGTERM,old_term)
        if transcript:transcript.close()
        os.close(master)
        if child_status is None:
            ended,status=os.waitpid(pid,os.WNOHANG)
            if not ended:
                try:os.killpg(pid,signal.SIGHUP)
                except ProcessLookupError:pass
                deadline=time.monotonic()+2
                while time.monotonic()<deadline:
                    ended,status=os.waitpid(pid,os.WNOHANG)
                    if ended:break
                    time.sleep(.05)
                if not ended:
                    try:os.killpg(pid,signal.SIGKILL)
                    except ProcessLookupError:pass
                    _,status=os.waitpid(pid,0)
            child_status=status
    return os.waitstatus_to_exitcode(child_status)

def start(store, parent=None, actor="Human", record_output=False):
    if os.environ.get("SAIGEN_SESSION"):
        raise RecordError("Already inside a recorded session. Exit it before starting another.")
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise RecordError("saigen start requires an interactive terminal")
    shell=shutil.which("zsh")
    if not shell:raise RecordError("This version of saigen start requires zsh")
    if not store.db.exists():store.init()
    ident=sessions.begin(store,parent,actor,Path.cwd(),record_output)
    folder=store.home/"sessions"/ident
    folder.mkdir(parents=True,mode=0o700)
    transcript=folder/"output.log" if record_output else None
    env=os.environ.copy()
    env.update(SAIGEN_SESSION=ident,SAIGEN_PROJECT=str(store.root),SAIGEN_PYTHON=sys.executable)
    repo=str(Path(__file__).resolve().parent.parent)
    env["PYTHONPATH"]=repo+(os.pathsep+env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    user_zdot=env.get("ZDOTDIR",str(Path.home()))
    hooks=Path(__file__).with_name("shell")/"hooks.zsh"
    code=1
    interrupted=True
    try:
        with tempfile.TemporaryDirectory(prefix="saigen-zsh-") as config:
            config=Path(config)
            (config/".zshenv").write_text(
                "ZDOTDIR="+shlex.quote(user_zdot)+"\n"
                '[[ -r "$ZDOTDIR/.zshenv" ]] && source "$ZDOTDIR/.zshenv"\n'
                'export SAIGEN_USER_ZDOTDIR="$ZDOTDIR"\n'
                "ZDOTDIR="+shlex.quote(str(config))+"\n")
            (config/".zshrc").write_text(
                'ZDOTDIR="$SAIGEN_USER_ZDOTDIR"\n'
                '[[ -r "$ZDOTDIR/.zshrc" ]] && source "$ZDOTDIR/.zshrc"\n'
                "source "+shlex.quote(str(hooks))+"\n")
            env["ZDOTDIR"]=str(config)
            print("Recording project: "+str(store.root),flush=True)
            if record_output:
                print("Output transcript enabled: terminal output, including echoed commands, is stored without redaction.",flush=True)
            code=_forward(store,ident,[shell,"-i"],env,transcript)
            interrupted=False
    except KeyboardInterrupt:
        code=130
    finally:
        sessions.close(store,ident,interrupted,transcript)
    return max(0,code) if code>=0 else 128-code
