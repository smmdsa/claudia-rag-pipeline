"""The Docker stacks: measure them, and start the containers that already exist.

Two stacks. `rag` serves the search index. `board` serves the board page. Both are
optional, and the harness runs without either.

`session open` calls `status` when the RAG canary reports BROKEN. It then calls
`start`, which runs `docker compose start`. That command starts a container that
exists and is stopped. It takes seconds.

`start` never builds an image. A build needs the network and minutes, and a session
brief must stay fast and predictable. `python3 -m harness stack up` builds, and so
does `infra/rag/up.sh`. `session open` names that command when no container exists.
"""
import json
import os

from harness import env, ports
from harness.util import HarnessError, sh

STACKS = {
    "rag": os.path.join("infra", "rag", "docker-compose.yml"),
    "board": os.path.join("infra", "board", "docker-compose.yml"),
}

# The ports that each stack publishes, by the variable that overrides each one.
STACK_PORTS = {
    "rag": ("HARNESS_RAG_PORT", "HARNESS_RAG_STATE_PORT"),
    "board": ("HARNESS_BOARD_PORT",),
}

# `docker compose start` on a stopped container takes seconds. The cap catches a
# daemon that hangs, and it never caps a build: `start` does not build.
START_TIMEOUT = 90
PROBE_TIMEOUT = 20


def compose_file(root, name):
    if name not in STACKS:
        raise HarnessError("no stack %r. The stacks are: %s." % (name, ", ".join(sorted(STACKS))))
    return os.path.join(root, STACKS[name])


def _base(root, name):
    envp = os.path.join(root, env.PATH)
    if not os.path.exists(envp):
        env.write(root)
    return ["docker", "compose", "--env-file", envp, "-f", compose_file(root, name)]


def probe():
    """Return (ok, reason). Measure the CLI and the daemon, never one of the two."""
    code, out = sh(["docker", "version", "--format", "{{.Server.Version}}"], timeout=PROBE_TIMEOUT)
    if code == 127:
        return False, "docker is not on the PATH"
    if code == 124:
        return False, "docker did not answer in %ss" % PROBE_TIMEOUT
    if code != 0:
        return False, "the docker daemon does not answer: %s" % out.strip().splitlines()[-1] if out.strip() else "the docker daemon does not answer"
    return True, ""


def status(root, name="rag"):
    """Report every service of one stack: declared, present, and running."""
    path = compose_file(root, name)  # this names an unknown stack before it reads a table
    report = {"stack": name, "file": STACKS[name], "docker": False, "reason": "",
              "declared": [], "services": [], "running": [], "stopped": [], "absent": []}
    if not os.path.exists(path):
        report["reason"] = "%s does not exist. This repository holds no %s stack." % (STACKS[name], name)
        return report
    ok, reason = probe()
    report["docker"], report["reason"] = ok, reason
    if not ok:
        return report
    base = _base(root, name)
    code, out = sh(base + ["config", "--services"], cwd=root, timeout=PROBE_TIMEOUT)
    if code != 0:
        report["reason"] = "docker compose cannot read %s: %s" % (STACKS[name], out.strip().splitlines()[-1] if out.strip() else code)
        return report
    report["declared"] = [s.strip() for s in out.splitlines() if s.strip()]
    code, out = sh(base + ["ps", "-a", "--format", "json"], cwd=root, timeout=PROBE_TIMEOUT)
    if code != 0:
        report["reason"] = "docker compose ps failed: %s" % (out.strip().splitlines()[-1] if out.strip() else code)
        return report
    for line in out.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        published = []
        for pub in row.get("Publishers") or []:
            try:
                port = int(pub.get("PublishedPort") or 0)
            except (TypeError, ValueError):
                continue
            if port:
                published.append(port)
        report["services"].append({"service": row.get("Service"), "name": row.get("Name"),
                                   "state": row.get("State"), "health": row.get("Health") or "",
                                   "published": sorted(set(published))})
    present = {s["service"] for s in report["services"]}
    report["running"] = sorted(s["service"] for s in report["services"] if s["state"] == "running")
    report["stopped"] = sorted(s["service"] for s in report["services"] if s["state"] != "running")
    report["absent"] = sorted(s for s in report["declared"] if s not in present)
    return report


def start(root, name="rag"):
    """Start every container of one stack that exists and is stopped. Never build.

    Return the report of `status` after the command, plus `started` and `note`.
    """
    report = status(root, name)
    report["started"] = []
    report["note"] = ""
    if not report["docker"]:
        return report
    if report["absent"]:
        report["note"] = ("no container for %s. `start` never builds. Run `python3 -m harness stack up "
                          "--stack %s`, or `./infra/%s/up.sh`." % (", ".join(report["absent"]), name, name))
        return report
    if not report["stopped"]:
        return report
    code, out = sh(_base(root, name) + ["start"], cwd=root, timeout=START_TIMEOUT)
    if code != 0:
        report["note"] = "docker compose start failed: %s" % (out.strip().splitlines()[-1] if out.strip() else code)
        return report
    wanted = report["stopped"]
    after = status(root, name)
    after["started"] = sorted(s for s in wanted if s in after["running"])
    after["note"] = "" if len(after["started"]) == len(wanted) else \
        "%s did not reach the running state. Read `docker compose logs`." % \
        ", ".join(s for s in wanted if s not in after["running"])
    return after


def up(root, name="rag", gpu=False):
    """Build the image and start the stack. This takes minutes on a cold cache."""
    args = _base(root, name)
    if gpu and name == "rag":
        args += ["-f", os.path.join(root, "infra", "rag", "docker-compose.gpu.yml")]
    code, out = sh(args + ["up", "-d", "--build"], cwd=root, timeout=3600)
    if code != 0:
        raise HarnessError("docker compose up failed for the %s stack. %s. "
                           "Read the output, fix the cause, and run the command again."
                           % (name, out.strip().splitlines()[-1] if out.strip() else "exit %d" % code))
    return status(root, name)


def stop(root, name="rag"):
    """Stop every running container of one stack. Keep the containers and the volumes."""
    report = status(root, name)
    report["stopped_now"] = []
    if not report["docker"] or not report["running"]:
        return report
    wanted = list(report["running"])
    code, out = sh(_base(root, name) + ["stop"], cwd=root, timeout=START_TIMEOUT)
    if code != 0:
        report["note"] = "docker compose stop failed: %s" % (out.strip().splitlines()[-1] if out.strip() else code)
        return report
    after = status(root, name)
    after["stopped_now"] = sorted(s for s in wanted if s not in after["running"])
    return after


def port_report(root, name="rag"):
    """Report every port of one stack: free, held by this stack, or held by a stranger.

    `harness ports` binds a port to test it, so it cannot say who holds a taken port.
    A stack that already runs holds its own ports, and `docker compose up -d` on it is
    a no operation. A check that refuses that case tells the user to override a port
    that nothing else wants (law 11 measures the port, not the owner).
    """
    report = status(root, name)
    mine = set()
    for s in report["services"]:
        if s["state"] == "running":
            mine.update(s.get("published") or [])
    rows = []
    for var in STACK_PORTS.get(name, ()):
        port = ports.port_for(var)
        free = ports.is_free(port)
        rows.append({"var": var, "port": port, "free": free,
                     "mine": port in mine, "conflict": (not free) and port not in mine})
    report["ports"] = rows
    report["conflicts"] = [r["port"] for r in rows if r["conflict"]]
    return report


def port_text(r):
    if not r["docker"]:
        return "STACK %s: docker is not available. %s" % (r["stack"], r["reason"])
    lines = []
    for row in r.get("ports") or []:
        if row["conflict"]:
            state = "TAKEN by another process"
        elif row["mine"]:
            state = "held by this stack"
        else:
            state = "free"
        lines.append("  %-6s %-5d %-24s %s" % ("BUSY" if row["conflict"] else "ok",
                                               row["port"], row["var"], state))
    if r["conflicts"]:
        lines.append("A port is taken by another process. Override it in the environment, "
                     "or stop that process. Ports: %s." % ", ".join(str(p) for p in r["conflicts"]))
    return "\n".join(lines)


def brief_line(r):
    """One line for the session brief. Return "" when there is nothing to report."""
    if not r["docker"]:
        return "STACK: docker is not available. %s. The session runs without the index." % r["reason"]
    if r["reason"]:
        return "STACK: %s" % r["reason"]
    if r.get("started"):
        return "STACK: started %s. The index answers in a moment." % ", ".join(r["started"])
    if r.get("note"):
        return "STACK: %s" % r["note"]
    if r["stopped"]:
        return "STACK: %s is not running." % ", ".join(r["stopped"])
    return ""


def status_text(r):
    if r["reason"] and not r["declared"]:
        return "STACK %s: %s" % (r["stack"], r["reason"])
    lines = ["STACK %s (%s): %d of %d service(s) running"
             % (r["stack"], r["file"], len(r["running"]), len(r["declared"]))]
    for s in sorted(r["services"], key=lambda s: s["service"] or ""):
        mark = "up  " if s["state"] == "running" else "DOWN"
        lines.append("  %s %-12s %s%s" % (mark, s["service"], s["state"],
                                          " (%s)" % s["health"] if s["health"] else ""))
    for s in r["absent"]:
        lines.append("  GONE %-12s no container. Run `python3 -m harness stack up --stack %s`." % (s, r["stack"]))
    if r.get("started"):
        lines.append("  started: %s" % ", ".join(r["started"]))
    if r.get("note"):
        lines.append("  note: %s" % r["note"])
    return "\n".join(lines)
