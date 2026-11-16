"""Small terminal prompts; no third-party runtime dependencies."""
import os
import select
import sys


def color(text, code="36"):
    if ("NO_COLOR" in os.environ or os.environ.get("TERM") == "dumb"
            or not sys.stdin.isatty() or not sys.stdout.isatty()):
        return text
    return f"\033[{code}m{text}\033[0m"


def question(text, default=""):
    hint = color(f" [{default}]", "2") if default != "" else ""
    return color(text) + hint + ": "


def can_select():
    return (os.name == "posix" and sys.stdin.isatty() and sys.stdout.isatty()
            and os.environ.get("TERM") != "dumb")


def read_key(fd):
    value = os.read(fd, 1)
    if not value or value == b"\x04":
        raise EOFError
    if value == b"\x03":
        raise KeyboardInterrupt
    if value == b"\x1b":
        sequence = b""
        for _ in range(2):
            if not select.select([fd], [], [], .1)[0]:
                raise KeyboardInterrupt
            sequence += os.read(fd, 1)
        return {b"[A": "up", b"OA": "up", b"[B": "down", b"OB": "down"}.get(sequence, "")
    return value.decode("ascii", errors="ignore")


def checkboxes(title, options):
    """Select zero or more choices with arrows/Space; restore the terminal on exit."""
    import termios
    import tty

    fd = sys.stdin.fileno()
    previous = termios.tcgetattr(fd)
    selected = set()
    cursor = 0
    drawn = False

    def draw(focus):
        nonlocal drawn
        if drawn:
            sys.stdout.write(f"\033[{len(options)}A")
        for index, label in enumerate(options):
            line = ("> " if index == focus else "  ") + ("[x] " if index in selected else "[ ] ") + label
            if index == focus:
                line = color(line)
            elif index in selected:
                line = color(line, "32")
            sys.stdout.write("\r\033[2K" + line + "\n")
        sys.stdout.flush()
        drawn = True

    print(color(title))
    print(color("  Up/Down: move | Space: toggle | Enter: confirm | a: all | n: none", "2"))
    try:
        tty.setcbreak(fd)
        sys.stdout.write("\033[?25l")
        draw(cursor)
        while True:
            key = read_key(fd)
            if key in {"\r", "\n"}:
                draw(None)
                return [label for index, label in enumerate(options) if index in selected]
            if key == "up":
                cursor = (cursor - 1) % len(options)
            elif key == "down":
                cursor = (cursor + 1) % len(options)
            elif key == " ":
                selected.symmetric_difference_update({cursor})
            elif key.lower() == "a":
                selected = set(range(len(options)))
            elif key.lower() == "n":
                selected.clear()
            draw(cursor)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, previous)
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()
