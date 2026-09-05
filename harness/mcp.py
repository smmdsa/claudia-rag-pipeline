"""The link between this agent and the index.

Claude Code opens every MCP connection once, when its process starts. It never
retries. A container that starts later answers on its port and stays invisible to the
agent for the whole session. `harness/rag.py` measures the SERVER. This module
measures the LINK, and the two are not the same reading.

Measured on 2026-09-05: the agent started at 13:48:48 and the `rag` container at
16:51:11. The container answered every HTTP probe, the canary printed `warnings`, and
the agent held no search tool for the whole session. Design law 3: a path that still
exists does not prove that the path is correct.

A time that this module cannot read stays `unknown`, and the brief prints nothing.
A default value must never look like a measurement (law 7).
"""
import os
import re
import time
from datetime import datetime

from harness import stack
from harness.ports import port_for
from harness.util import human_delta, sh

# The process name of the client that holds the MCP connection. Linux truncates
# `comm` to 15 characters, and `claude` fits.
CLIENT_NAMES = ("claude",)
MAX_DEPTH = 20
PROBE_TIMEOUT = 8


def _uptime():
    """The seconds since the kernel booted. Linux only."""
    try:
        with open("/proc/uptime", encoding="utf-8") as fh:
            return float(fh.read().split()[0])
    except (OSError, ValueError, IndexError):
        return None


def _proc_linux(pid):
    """Read (ppid, elapsed seconds, name) from /proc, or None."""
    up = _uptime()
    if up is None or not hasattr(os, "sysconf"):
        return None
    try:
        with open("/proc/%d/stat" % pid, "rb") as fh:
            text = fh.read().decode("utf-8", "replace")
        # The command sits in parentheses and can hold a space. Read after the last one.
        fields = text[text.rindex(")") + 2:].split()
        ppid = int(fields[1])
        ticks = float(fields[19])
        with open("/proc/%d/comm" % pid, "rb") as fh:
            name = fh.read().decode("utf-8", "replace").strip()
        hz = float(os.sysconf("SC_CLK_TCK") or 100)
    except (OSError, ValueError, IndexError):
        return None
    return ppid, up - ticks / hz, name


def elapsed_seconds(text):
    """Read the POSIX elapsed time `[[dd-]hh:]mm:ss`. Return None when it does not parse."""
    found = re.match(r"^(?:(\d+)-)?(?:(\d+):)?(\d+):(\d+)$", (text or "").strip())
    if not found:
        return None
    days, hours, minutes, seconds = (int(g or 0) for g in found.groups())
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def _proc_ps(pid):
    """Read (ppid, elapsed seconds, name) with `ps`, for the systems with no /proc."""
    code, out = sh(["ps", "-o", "ppid=,etime=,comm=", "-p", str(pid)], timeout=PROBE_TIMEOUT)
    if code != 0:
        return None
    parts = out.strip().split(None, 2)
    if len(parts) < 3:
        return None
    elapsed = elapsed_seconds(parts[1])
    if elapsed is None:
        return None
    try:
        ppid = int(parts[0])
    except ValueError:
        return None
    return ppid, elapsed, os.path.basename(parts[2].strip())


def proc(pid):
    """Read one process. /proc first, because it carries the exact start tick.

    The reading is an ELAPSED time and never an absolute one. `/proc/stat` holds a
    `btime` that drifts with every clock correction: it placed this agent 40 seconds
    early on 2026-09-05. The caller subtracts the elapsed time from the wall clock,
    so the agent and the container are read against the same clock.
    """
    if os.path.isdir("/proc/%d" % pid):
        info = _proc_linux(pid)
        if info is not None:
            return info
    return _proc_ps(pid)


def agent_started_at(pid=None, now=None):
    """Return the epoch second when the Claude Code process started, or None.

    Walk the parents of this command. The harness runs as a child of the client, so
    the client is an ancestor. A command that runs outside the client finds no
    ancestor and returns None.
    """
    pid = os.getpid() if pid is None else pid
    now = time.time() if now is None else now
    seen = set()
    for _ in range(MAX_DEPTH):
        if pid <= 1 or pid in seen:
            return None
        seen.add(pid)
        info = proc(pid)
        if info is None:
            return None
        ppid, elapsed, name = info
        if name.lower() in CLIENT_NAMES:
            return now - elapsed
        pid = ppid
    return None


def parse_rfc3339(text):
    """Read the timestamp that `docker inspect` prints. Return None when it is not a time.

    Docker prints nine fraction digits, and `datetime` reads six. It prints
    `0001-01-01T00:00:00Z` for a container that never ran.
    """
    text = (text or "").strip()
    found = re.match(r"^(\d{4}-\d\d-\d\d)[T ](\d\d:\d\d:\d\d)(?:\.(\d+))?(Z|[+-]\d\d:?\d\d)$", text)
    if not found or text.startswith("0001-01-01"):
        return None
    date, clock, fraction, zone = found.groups()
    fraction = (fraction or "0")[:6].ljust(6, "0")
    if zone == "Z":
        zone = "+00:00"
    elif ":" not in zone:
        zone = zone[:3] + ":" + zone[3:]
    try:
        return datetime.fromisoformat("%sT%s.%s%s" % (date, clock, fraction, zone)).timestamp()
    except ValueError:
        return None


def index_started_at(root, name="rag", port=None):
    """Return the epoch second when the container that publishes the MCP port started.

    The stack holds more than one container. Only the one that serves the MCP port
    holds the connection, so this reads that one and never the newest.
    """
    port = port_for("HARNESS_RAG_PORT") if port is None else port
    report = stack.status(root, name)
    if not report.get("docker"):
        return None
    for service in report.get("services") or []:
        if service.get("state") != "running" or not service.get("name"):
            continue
        if port not in (service.get("published") or []):
            continue
        code, out = sh(["docker", "inspect", "--format", "{{.State.StartedAt}}", service["name"]],
                       timeout=PROBE_TIMEOUT)
        if code != 0:
            return None
        return parse_rfc3339(out)
    return None


def link_state(root, name="rag", agent=None, index=None, now=None):
    """Did the index start after this agent? Return `live`, `stale`, or `unknown`."""
    report = {"state": "unknown", "reason": "", "agent_started": None, "index_started": None, "gap": None}
    agent = agent_started_at(now=now) if agent is None else agent
    if agent is None:
        report["reason"] = "no Claude Code process is a parent of this command"
        return report
    report["agent_started"] = agent
    index = index_started_at(root, name) if index is None else index
    if index is None:
        report["reason"] = "the start time of the container that serves the MCP port is not measured"
        return report
    report["index_started"] = index
    report["gap"] = index - agent
    report["state"] = "stale" if index > agent else "live"
    return report


def link_line(report):
    """One line for the brief. An empty string when the link is live or not measured."""
    if report.get("state") != "stale":
        return ""
    return ("MCP: the index started %s after this agent, so this session holds no search tool. "
            "Claude Code opens an MCP connection once, and it never retries. "
            "Leave the containers up and restart Claude Code." % human_delta(report["gap"]))


def link_text(report):
    """The full report for `python3 -m harness rag link`."""
    head = {"live": "MCP: live", "stale": "MCP: stale", "unknown": "MCP: not measured"}[report["state"]]
    lines = [head]
    if report["reason"]:
        lines.append("  " + report["reason"])
    line = link_line(report)
    if line:
        lines.append("  " + line[len("MCP: "):])
    for label, key in (("agent started", "agent_started"), ("index started", "index_started")):
        value = report.get(key)
        stamp = datetime.fromtimestamp(value).isoformat(timespec="seconds") if value else "not measured"
        lines.append("  %-14s %s" % (label, stamp))
    return "\n".join(lines)
