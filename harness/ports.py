"""Port checks. Every port is tested before use.

A taken port reports the port, the process that holds it when `ss` or `lsof` exists,
and the environment variable that overrides it.
"""
import os
import re
import socket

from harness.util import sh

DEFAULTS = {
    "HARNESS_RAG_PORT": (8410, "RAG MCP server"),
    "HARNESS_RAG_STATE_PORT": (8411, "RAG index state"),
    "HARNESS_BOARD_PORT": (8412, "board dashboard"),
}


def env_file_port(var, root=None):
    """The port that `.harness/env.local` declares, or None.

    `harness/env.py` imports this module, so the import sits inside the call. One
    parser reads the file, and it lives in `env.read` (law 2).
    """
    from harness import env  # late: env imports DEFAULTS from this module
    try:
        raw = env.read(root or os.getcwd()).get(var)
    except OSError:
        return None
    return int(raw) if raw and raw.isdigit() else None


def port_for(var, root=None):
    """The port for one variable. The shell wins, then `.harness/env.local`, then the default.

    `harness/stack.py` runs `docker compose --env-file .harness/env.local`, and compose
    gives the shell precedence over that file. This function follows the same order, so
    the checker measures the port that the stack really publishes (law 11).

    Before this, `port_for` read the shell alone. A port that the user overrode in the
    file was invisible: `harness ports` checked 8410 while docker published 9410. The
    two agreed only while the override matched the default (law 3).
    """
    raw = os.environ.get(var)
    if raw and raw.isdigit():
        return int(raw)
    found = env_file_port(var, root)
    return DEFAULTS[var][0] if found is None else found


def is_free(port, host="127.0.0.1"):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((host, port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def holder(port):
    """Name the process on the port. Return (text, measured)."""
    code, out = sh(["ss", "-ltnp"], timeout=10)
    if code == 0:
        for line in out.splitlines():
            if re.search(r":%d\s" % port, line):
                m = re.search(r'users:\(\("([^"]+)",pid=(\d+)', line)
                if m:
                    return "%s (pid %s)" % (m.group(1), m.group(2)), True
                return "a process that ss cannot name (run ss -ltnp as root)", True
        return "no listener seen by ss", True
    code, out = sh(["lsof", "-nP", "-iTCP:%d" % port, "-sTCP:LISTEN"], timeout=10)
    if code == 0 and out.strip():
        rows = out.strip().splitlines()
        if len(rows) > 1:
            cols = rows[1].split()
            return "%s (pid %s)" % (cols[0], cols[1]), True
    return "not measured (no ss and no lsof)", False


def check_ports(vars_=None, root=None):
    rows = []
    for var in vars_ or DEFAULTS:
        port = port_for(var, root)
        free = is_free(port)
        row = {"variable": var, "port": port, "service": DEFAULTS[var][1], "free": free,
               "default": DEFAULTS[var][0], "holder": None}
        if not free:
            row["holder"], _ = holder(port)
        rows.append(row)
    return rows


def ports_text(rows):
    lines = []
    for r in rows:
        if r["free"]:
            lines.append("  free   %5d  %-18s (%s)" % (r["port"], r["service"], r["variable"]))
        else:
            lines.append("  TAKEN  %5d  %-18s held by %s. Override with %s=<port>."
                         % (r["port"], r["service"], r["holder"], r["variable"]))
    return "\n".join(lines)


def all_free(rows):
    return all(r["free"] for r in rows)
