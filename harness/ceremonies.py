"""The ceremonies: plan, triage, review, retro.

Each ceremony reads measured data and writes one document with an agenda and open
questions. The answers belong to the user. A ceremony never writes a verdict.
"""
import datetime as _dt
import os

from harness import journal, state
from harness.board import all_tasks, next_tasks, ready, scan, summary, why_not_ready
from harness.clock import days_remaining, overdue, sprint_status
from harness.util import HarnessError, now, parse_iso, rel, sh, today, write_text

WORK_HOURS = {"XS": 0.25, "S": 1, "M": 4, "L": 12, "XL": None}
EYE_MINUTES = {"NONE": 0, "GLANCE": 5, "RUN": 30}


def _latest_sprint(tree):
    return tree.sprints[-1] if tree.sprints else None


def _sprint(tree, sprint_id):
    if sprint_id:
        for sp in tree.sprints:
            if sp.id == sprint_id or sp.dir == sprint_id:
                return sp
        raise HarnessError("no sprint with id %s" % sprint_id)
    return _latest_sprint(tree)


def _sizes(tasks):
    work = sum(WORK_HOURS.get(t.work) or 0 for t in tasks)
    unsized = [t.id for t in tasks if WORK_HOURS.get(t.work) is None]
    eye = sum(EYE_MINUTES.get(t.eye, 0) for t in tasks)
    return work, unsized, eye


def _targets_line(root):
    rows = state.measure(root)
    over = ["%s %s > %s" % (r["stock"], r["current"], r["target"]) for r in rows if r["over"]]
    return over


def _head(title, root):
    return ["# %s — %s" % (title, today().isoformat()), "",
            "> Computed by `python3 -m harness ceremony` from the folder tree, the journal, and git.",
            "> The questions are open. The user answers them. This document holds no verdict.", ""]


# ---------------------------------------------------------------- plan

def plan(root, sprint_id=None):
    tree = scan(root)
    sp = _sprint(tree, sprint_id)
    lines = _head("Sprint planning", root)
    if sp:
        lines.append("Sprint under planning: **%s — %s** (%s .. %s)." % (sp.id, sp.title, sp.starts or "?", sp.ends or "?"))
        left = [t for e in sp.epics for t in e.tasks if t.state != "done"]
        w, unsized, e = _sizes(left)
        lines.append("Open work already inside: %d task(s), about %.1f h of agent work and %d min of eye." % (len(left), w, e))
    else:
        lines.append("No sprint exists. Create one: `python3 -m harness new sprint --title ... --starts ... --ends ...`.")
    lines.append("")
    lines.append("## Candidates from the backlog (%d)" % len(tree.backlog))
    lines.append("")
    if tree.backlog:
        lines.append("| id | title | work | eye | owner | due | ready |")
        lines.append("|---|---|---|---|---|---|---|")
        for t in sorted(tree.backlog, key=lambda t: (t.due or "9999", t.id)):
            lines.append("| %s | %s | %s | %s | %s | %s | %s |" % (
                t.id, t.title, t.work, t.eye, t.owner, t.due or "", "yes" if ready(t, tree) else why_not_ready(t, tree) or "no"))
        w, unsized, e = _sizes(tree.backlog)
        lines.append("")
        lines.append("Total if everything enters: about %.1f h of agent work and %d min of eye. XL tasks not counted: %s."
                     % (w, e, ", ".join(unsized) or "none"))
    else:
        lines.append("The backlog is empty.")
    roadmap = os.path.join(root, "work", "ROADMAP.md")
    lines.append("")
    lines.append("## Roadmap")
    lines.append("")
    lines.append("`work/ROADMAP.md` %s. Read it before you pick." % ("exists" if os.path.exists(roadmap) else "is missing"))
    over = _targets_line(root)
    lines.append("")
    lines.append("## Targets missed right now")
    lines.append("")
    lines.extend(["- " + o for o in over] or ["- none"])
    lines.append("")
    lines.append("## Questions for the user")
    lines.append("")
    lines.append("1. Which candidates enter the sprint? Name them by id.")
    lines.append("2. Which epic holds each one? `python3 -m harness assign TASK-NNNN --epic EP-NN`.")
    lines.append("3. Is the eye budget realistic for the sprint dates? The eye is the bottleneck, not the agent.")
    lines.append("4. Which task is first? Set `priority: 1` from the user's words, never from the agent's.")
    return "plan", "\n".join(lines) + "\n"


# ---------------------------------------------------------------- triage

def _first_commit_age(root, path):
    code, out = sh(["git", "log", "--format=%at", "--diff-filter=ACR", "--", os.path.relpath(path, root)], cwd=root, timeout=30)
    if code != 0 or not out.strip():
        return None
    stamps = [int(x) for x in out.split() if x.isdigit()]
    if not stamps:
        return None
    return (now().timestamp() - min(stamps)) / 86400.0


def triage(root):
    tree = scan(root)
    lines = _head("Backlog triage", root)
    problems = []
    for t in tree.backlog:
        why = []
        if t.work not in ("XS", "S", "M", "L"):
            why.append("work %s" % t.work)
        if t.eye not in ("NONE", "GLANCE", "RUN"):
            why.append("eye %s" % t.eye)
        if t.owner == "user" and not t.due:
            why.append("owner user with no due date")
        if t.decision:
            why.append("waits decision %s" % t.decision)
        for b in t.blocked_by:
            why.append("blocked by %s" % b)
        age = _first_commit_age(root, t.path)
        if age is None:
            why.append("age not measured (not committed)")
        elif age > 30:
            why.append("%d days old" % int(age))
        problems.append((t, why, age))
    lines.append("## Backlog (%d task(s))" % len(tree.backlog))
    lines.append("")
    lines.append("| id | title | work | eye | owner | age (d) | flags |")
    lines.append("|---|---|---|---|---|---|---|")
    for t, why, age in problems:
        lines.append("| %s | %s | %s | %s | %s | %s | %s |" % (
            t.id, t.title, t.work, t.eye, t.owner, "not measured" if age is None else "%d" % int(age), "; ".join(why)))
    lines.append("")
    lines.append("## Questions for the user")
    lines.append("")
    lines.append("1. Which flagged tasks are still wanted? Remove the rest with `git rm`.")
    lines.append("2. Which decisions above can the user close today?")
    lines.append("3. Which XL tasks split into S or M tasks?")
    return "triage", "\n".join(lines) + "\n"


# ---------------------------------------------------------------- review

def review(root, sprint_id=None):
    tree = scan(root)
    sp = _sprint(tree, sprint_id)
    if sp is None:
        raise HarnessError("no sprint to review.")
    tasks = [t for e in sp.epics for t in e.tasks]
    s = summary(tasks)
    lines = _head("Sprint review — %s" % sp.id, root)
    left = days_remaining(sp)
    lines.append("**%s — %s** · status %s · %s" % (sp.id, sp.title, sprint_status(sp),
                                                   "no dates" if left is None else ("%d d remain" % left if left >= 0 else "ended %d d ago" % -left)))
    lines.append("")
    lines.append("- done %d/%d · in progress %d · todo %d" % (s["done"], s["total"], s["in_progress"], s["todo"]))
    if sprint_status(sp) == "ended" and s["total"] - s["done"]:
        lines.append("- OVERDUE: the sprint ended on %s with %d open task(s). The date does not move. The user decides: close, carry over, or drop." % (sp.ends, s["total"] - s["done"]))
    lines.append("")
    lines.append("## Awaiting a human verdict (%d)" % s["awaiting_verdict"])
    lines.append("")
    for t in tasks:
        if t.state == "in-progress" and t.needs_eye():
            lines.append("- %s — %s (eye %s). Close it with `python3 -m harness done %s --verdict \"<words>\" --by user`."
                         % (t.id, t.title, t.eye, t.id))
    lines.append("")
    lines.append("## Done in this sprint")
    lines.append("")
    for e in sp.epics:
        for t in e.tasks:
            if t.state == "done":
                lines.append("- %s — %s (%s/%s)%s" % (t.id, t.title, t.work, t.eye, "" if not t.needs_eye() else (" verdict recorded" if t.has_verdict() else " NO VERDICT")))
    lines.append("")
    lines.append("## Still open")
    lines.append("")
    for e in sp.epics:
        for t in e.tasks:
            if t.state != "done":
                lines.append("- %s — %s [%s]%s" % (t.id, t.title, t.state, (" · " + why_not_ready(t, tree)) if t.state == "todo" and not ready(t, tree) else ""))
    lines.append("")
    lines.append("## Questions for the user")
    lines.append("")
    lines.append("1. For each task that awaits a verdict: ok, not ok, or partial? In your words.")
    lines.append("2. Does each open task carry over, or leave the sprint?")
    lines.append("3. What did the end user gain? Name the check that showed it.")
    return "review", "\n".join(lines) + "\n"


# ---------------------------------------------------------------- retro

def retro(root, sprint_id=None):
    tree = scan(root)
    sp = _sprint(tree, sprint_id)
    lines = _head("Retrospective%s" % (" — " + sp.id if sp else ""), root)
    sessions = journal.sessions(root)
    observations = journal.observations(root)
    start = end = None
    if sp and sp.starts and sp.ends:
        start = _dt.datetime.combine(_dt.date.fromisoformat(sp.starts), _dt.time.min).astimezone()
        end = _dt.datetime.combine(_dt.date.fromisoformat(sp.ends), _dt.time.max).astimezone()

    def inside(line):
        if start is None:
            return True
        try:
            ts = parse_iso(line["ts"])
        except (KeyError, ValueError):
            return False
        return start <= ts <= end

    sess = [l for l in sessions if inside(l)]
    obs = [l for l in observations if inside(l)]
    closed = sum(len(l.get("qa_closed") or []) for l in sess)
    opened = sum(len(l.get("qa_open") or []) for l in sess)
    empty = sum(1 for l in sess if not (l.get("qa_closed") or []))
    lines.append("Source: `.harness/journal.jsonl`%s. The agent memory is not a measurement." % (
        " between %s and %s" % (sp.starts, sp.ends) if start else ""))
    lines.append("")
    lines.append("- sessions: %d" % len(sess))
    lines.append("- verdicts closed: %d · items left open at a close: %d" % (closed, opened))
    lines.append("- sessions that closed no verdict: %d%s" % (empty, " — two in a row are a pattern, not noise" if empty >= 2 else ""))
    lines.append("- commits recorded at the closes: %s" % (sum(l.get("commits") or 0 for l in sess)))
    lines.append("- observations of a missed target: %d" % len(obs))
    lines.append("")
    lines.append("## Surprises the sessions recorded")
    lines.append("")
    surprises = [s for l in sess for s in (l.get("surprises") or [])]
    lines.extend(["- " + s for s in surprises] or ["- none recorded"])
    lines.append("")
    lines.append("## What failed")
    lines.append("")
    failed = [s for l in sess for s in (l.get("failed") or [])]
    lines.extend(["- " + s for s in failed] or ["- none recorded"])
    lines.append("")
    lines.append("## Missed targets")
    lines.append("")
    by_stock = {}
    for o in obs:
        by_stock.setdefault(o.get("stock"), []).append(o)
    lines.extend(["- %s: %d observation(s), last current %s against target %s" % (k, len(v), v[-1].get("current"), v[-1].get("target"))
                  for k, v in by_stock.items()] or ["- none"])
    lines.append("")
    lines.append("## Questions for the user")
    lines.append("")
    lines.append("1. Which surprise changes a rule? Write the rule in one place.")
    lines.append("2. Which missed target is a wrong target, and which is a real gap?")
    lines.append("3. What does the next sprint stop doing?")
    return "retro", "\n".join(lines) + "\n"


CEREMONIES = {"plan": plan, "triage": triage, "review": review, "retro": retro}


def run(root, name, sprint_id=None, write=False):
    fn = CEREMONIES.get(name)
    if fn is None:
        raise HarnessError("unknown ceremony %s. Use one of %s." % (name, ", ".join(CEREMONIES)))
    kind, text = fn(root, sprint_id) if name != "triage" else fn(root)
    path = None
    if write:
        tree = scan(root)
        sp = _sprint(tree, sprint_id) if name != "triage" else _latest_sprint(tree)
        folder = os.path.join(sp.path, "ceremonies") if sp else os.path.join(root, "work", "ceremonies")
        path = os.path.join(folder, "%s-%s.md" % (today().isoformat(), kind))
        write_text(path, text)
        path = rel(root, path)
    return {"ceremony": kind, "path": path, "text": text}
