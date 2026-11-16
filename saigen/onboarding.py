"""Terminal setup interview and saved local viewer settings."""
import json
import shlex
import socket
import sys

from .store import RecordError, text
from .workspace import ADAPTERS, PERMISSIONS, prepare, write_files
from .terminal import can_select, checkboxes, color, question

DEFAULT_PORT = 8767


def valid_port(value):
    if type(value) not in (int, str):
        raise RecordError("Choose a port number from 1 to 65535.")
    try:
        port = int(value)
    except (TypeError, ValueError) as exc:
        raise RecordError("Choose a port number from 1 to 65535.") from exc
    if not 1 <= port <= 65535:
        raise RecordError("Choose a port number from 1 to 65535.")
    return port


def saved_port(store):
    path = store.home / "viewer.json"
    if not path.exists():
        return DEFAULT_PORT
    try:
        settings = json.loads(path.read_text())
        return valid_port(settings["port"])
    except (ValueError, KeyError, TypeError) as exc:
        raise RecordError("Invalid viewer settings: " + str(path)) from exc


def port_available(port):
    try:
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False


def suggested_port(start=DEFAULT_PORT):
    for port in range(start, min(start + 100, 65536)):
        if port_available(port):
            return port
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def ask(prompt, default=""):
    answer = input(question(prompt, str(default))).strip()
    return answer or str(default)


def yes_no(prompt, default=True):
    while True:
        answer = input(question(prompt, "Y/n" if default else "y/N")).strip().lower()
        if not answer:
            return default
        if answer in {"y", "yes"}:
            return True
        if answer in {"n", "no"}:
            return False
        print("Enter yes or no.")


def choose_agents():
    agents = list(ADAPTERS)
    if can_select():
        return checkboxes("AI agents", agents)
    print(color("AI agents"))
    return [agent for agent in agents if yes_no("Set up " + agent + "?", default=False)]


def choose_permission():
    print(color("Agent workflow permissions:"))
    print("  1 Ask before downloads and analysis runs.")
    print("  2 Flexible: requested edits, public-data downloads, and analysis runs may proceed without separate approval.")
    print("This saves instructions. Your agent's filesystem and network permissions still apply.")
    while True:
        answer = ask("Choose 1 or 2", "1").lower()
        if answer in {"1", "ask"}:
            return "ask"
        if answer in {"2", "flexible"}:
            return "flexible"
        print("Choose 1 or 2.")


def initialize(store, *, name=None, agents=None, port=None, permission=None,
               non_interactive=False, start_viewer=None, ui_development=None):
    interactive = not non_interactive and sys.stdin.isatty() and sys.stdout.isatty()
    if store.db.exists():
        result = store.flow()
        if interactive:
            print(f"Project already initialized: {result['project']}. Existing settings were retained.")
            print("Use saigen setup to add an agent, or saigen serve to open the viewer.")
            print("Viewer command: " + viewer_command(store, saved_port(store)))
        else:
            print(json.dumps(result, indent=2))
        return 0
    try:
        if interactive:
            print("Set up SaigenBio in " + str(store.root))
            if name is None:
                name = ask("Project name", store.root.name)
            if agents is None:
                agents = choose_agents()
            if agents and permission is None:
                permission = choose_permission()
            if agents and ui_development is None:
                ui_development = "allow" if yes_no("Allow routine local SaigenBio UI source fixes and improvements?", default=False) else "ask"
            if port is None:
                proposal = suggested_port()
                while True:
                    try:
                        port = valid_port(ask("Viewer port", proposal))
                    except RecordError as exc:
                        print(exc)
                        continue
                    if port_available(port):
                        break
                    print(f"Port {port} is in use. The existing service will be left running.")
                    proposal = suggested_port(port if port < 65535 else DEFAULT_PORT)
            if start_viewer is None:
                start_viewer = yes_no("Start the viewer now?")
        name = text(name or store.root.name, "project name", 120, True)
        agents = agents or []
        permission = permission or "ask"
        ui_development = ui_development or "ask"
        if permission not in PERMISSIONS:
            raise RecordError("Unknown workflow permission mode")
        port = valid_port(port if port is not None else suggested_port())
        if not port_available(port):
            if not interactive:
                raise RecordError(f"Port {port} is in use. Choose another --port; no existing service was stopped.")
            raise RecordError(f"Port {port} became unavailable. Run init again and choose another port.")
        viewer = f"http://127.0.0.1:{port}/"
        root, files, context = prepare(store.root, agents, ".", [], viewer, permission, ui_development)
        if (store.home / "viewer.json").exists():
            raise RecordError("Existing viewer settings found without an initialized project. Review .saigen/viewer.json before initializing.")
        if interactive:
            print(f"\nProject: {name}\nAgents: {', '.join(agents) or 'none'}\nViewer: {viewer}")
            if agents:
                print("Workflow permissions: " + permission)
                print("SaigenBio UI development: " + ui_development)
            print("Start viewer: " + ("yes" if start_viewer else "no"))
            if not yes_no("Create this workspace?"):
                print("Cancelled. No files were changed.")
                return 0
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled. No files were changed.")
        return 130
    result = store.init(name)
    write_files(root, files)
    (store.home / "viewer.json").write_text(json.dumps({"port": port}, indent=2) + "\n")
    if interactive:
        print(color(f"\nProject ready. Viewer: {viewer}", "32"))
        print("Viewer command: " + viewer_command(store, port))
        if agents:
            print("Open this folder in your selected AI agent to begin.")
            print("Host permissions: allow workspace writes and, for downloads, network access in your agent's permission settings.")
            if "codex" in agents:
                print("Codex permission guidance: https://learn.chatgpt.com/docs/agent-approvals-security")
        if not start_viewer:
            print("Run that command when you want to start the viewer.")
    else:
        result["workspaceSetup"] = {"agents": context["agents"], "permissionMode": permission, "uiDevelopment": ui_development, "viewer": viewer}
        print(json.dumps(result, indent=2), flush=True)
    if start_viewer:
        from .server import serve
        print("Leave this terminal running; press Ctrl+C to stop the viewer.", flush=True)
        serve(store, port)
    return 0


def viewer_command(store, port):
    return shlex.join(["saigen", "serve", "--project", str(store.root), "--port", str(port)])
