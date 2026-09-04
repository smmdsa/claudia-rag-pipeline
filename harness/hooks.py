"""The hook entry points. `.claude/settings.json` calls `python3 -m harness hook <name>`.

Every hook reads the JSON payload on stdin. `docs/HOOKS.md` records the payload
shapes. A hook never breaks a session: an unexpected payload prints a line and exits 0.
A deny prints the documented JSON and exits 0. Feedback after a tool ran prints to
stderr and exits 2.
"""
import json
import os
import re
import sys

from harness import board, manifest, scaffold, state
from harness.board import all_tasks, scan
from harness.clock import overdue
from harness.util import rel

STATE_FOLDER = re.compile(r"(^|/)work/sprints/[^/]+/epic-[^/]+/(todo|in-progress|done)/[^/]+$")
TOOL_OWNED = (".harness/manifest.json", ".harness/journal.jsonl", ".harness/board.sqlite")
USER_OWNED = (".harness/targets.json",)
TASK_FILE = re.compile(r"(^|/)work/.*TASK-\d{4}[^/]*\.md$")
PRIORITY_LINE = re.compile(r"^\s*priority(-[a-z]+)?\s*:.*$", re.M)
MOVE_ON_WORK = re.compile(r"(^|[\s;&|(])(mv|cp|rm|rmdir)\s[^;&|]*\bwork/(sprints|backlog)\b")
GIT_MV_ON_WORK = re.compile(r"\bgit\s+(mv|rm)\s[^;&|]*\bwork/")


def read_payload(stream=None):
    raw = (stream or sys.stdin).read()
    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except ValueError:
        return {}


def _deny(reason):
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                              "permissionDecision": "deny",
                                              "permissionDecisionReason": reason}}))
    return 0


def _relpath(root, file_path):
    if not file_path:
        return None
    p = file_path if os.path.isabs(file_path) else os.path.join(root, file_path)
    p = os.path.realpath(p)
    r = os.path.realpath(root)
    if not p.startswith(r + os.sep):
        return None
    return os.path.relpath(p, r).replace(os.sep, "/")


def session_start(root, payload):
    report = manifest.doctor(root)
    if report["state"] == "not-initialised":
        r = scaffold.init(root)
        print("harness: the repository was not initialised. init created %d file(s): %s"
              % (len(r["created"]), ", ".join(r["created"][:8]) + (" ..." if len(r["created"]) > 8 else "")))
        report = manifest.doctor(root)
    print(manifest.doctor_text(report))
    print("harness: open the session with `python3 -m harness session open`.")
    return 0


def pre_write(root, payload):
    tool = payload.get("tool_name", "")
    rp = _relpath(root, (payload.get("tool_input") or {}).get("file_path"))
    if rp is None:
        return 0
    if rp in TOOL_OWNED:
        return _deny("%s is written by the harness tool only. Use `python3 -m harness` commands." % rp)
    if rp in USER_OWNED:
        return _deny("%s is user-owned. If the user gave this target in their own words, run "
                     "`python3 -m harness target set <stock> <value> --by user --why \"...\"`." % rp)
    if STATE_FOLDER.search(rp) and tool == "Write" and not os.path.exists(os.path.join(root, rp)):
        return _deny("%s is inside a state folder. The folder is the state. Create a task with "
                     "`python3 -m harness new task --title ... --epic EP-NN`, and move it with start/done/back." % rp)
    if TASK_FILE.search(rp) and _priority_lines_change(payload):
        task_id = re.search(r"TASK-\d{4}", rp).group(0)
        return _deny("this write sets or changes `priority` in %s by hand. A priority carries an author and a "
                     "date, and the user names it. Run `python3 -m harness priority %s --by user --why \"...\"`."
                     % (rp, task_id))
    return 0


def _priority_lines(text):
    return sorted(m.group(0).strip() for m in PRIORITY_LINE.finditer(text or ""))


def _priority_lines_change(payload):
    """True when the written text adds, removes, or changes a `priority*:` line."""
    inp = payload.get("tool_input") or {}
    if payload.get("tool_name") == "Write":
        return bool(_priority_lines(inp.get("content")))
    return _priority_lines(inp.get("new_string")) != _priority_lines(inp.get("old_string"))


def pre_bash(root, payload):
    cmd = (payload.get("tool_input") or {}).get("command", "") or ""
    if MOVE_ON_WORK.search(cmd) or GIT_MV_ON_WORK.search(cmd):
        return _deny("this command moves or removes files under work/ by hand. The folder is the state. "
                     "Use `python3 -m harness start|done|back|assign`, or `git rm` through the user.")
    return 0


def _touches_work(root, payload):
    tool = payload.get("tool_name", "")
    inp = payload.get("tool_input") or {}
    if tool in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        rp = _relpath(root, inp.get("file_path"))
        return bool(rp and rp.startswith("work/"))
    if tool == "Bash":
        cmd = inp.get("command", "") or ""
        return "work/" in cmd or "-m harness" in cmd
    return False


def post_work(root, payload):
    if not _touches_work(root, payload):
        return 0
    if not os.path.isdir(os.path.join(root, "work")):
        return 0
    tree = scan(root)
    errors, warnings = board.check(tree, wip_cap=state.wip_cap(root))
    if errors:
        sys.stderr.write("harness check is RED after this change:\n")
        for e in errors:
            sys.stderr.write("  error " + e + "\n")
        for w in warnings:
            sys.stderr.write("  warn  " + w + "\n")
        return 2
    print("harness check: GREEN (%d task(s), %d warning(s))" % (len(all_tasks(tree)), len(warnings)))
    for w in warnings:
        print("  warn  " + w)
    return 0


def stop(root, payload):
    if payload.get("stop_hook_active"):
        return 0
    if not os.path.isdir(os.path.join(root, "work")):
        return 0
    tree = scan(root)
    waiting = [t for t in all_tasks(tree) if t.state == "in-progress" and t.needs_eye()]
    late = overdue(tree)
    if not waiting and not late:
        return 0
    parts = []
    if waiting:
        parts.append("%d task(s) wait for a human verdict: %s" % (len(waiting), ", ".join(t.id for t in waiting)))
    for sp, left in late:
        parts.append("%s ended on %s with %d open task(s)" % (sp.id, sp.ends, len(left)))
    print(json.dumps({"systemMessage": "harness: " + ". ".join(parts) + "."}))
    return 0


def session_end(root, payload):
    if not manifest.exists(root):
        return 0
    written = state.observe(root)
    if written:
        print("harness: %d observation(s) appended to %s" % (len(written), rel(root, os.path.join(root, ".harness", "journal.jsonl"))))
    return 0


HOOKS = {
    "session-start": session_start,
    "pre-write": pre_write,
    "pre-bash": pre_bash,
    "post-work": post_work,
    "stop": stop,
    "session-end": session_end,
}


def run(root, name, stream=None):
    fn = HOOKS.get(name)
    if fn is None:
        print("harness hook: unknown hook %s. Known: %s" % (name, ", ".join(HOOKS)))
        return 0
    payload = read_payload(stream)
    try:
        return fn(root, payload)
    except Exception as exc:  # a hook never breaks the session
        print("harness hook %s: %s" % (name, exc))
        return 0
