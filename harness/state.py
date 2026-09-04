"""Targets, computed state, and the gap between them.

Three files, three owners:
  .harness/targets.json     the USER declares targets. `target set` is the only writer.
  harness state             computes every value on each run. It stores nothing.
  .harness/escalations.md   the agent writes what it cannot decide. Never the decision.

A default value must never look like a measurement. A stock that the tool cannot
measure carries `current: None` and a `reason`.
"""
import datetime as _dt
import json
import os

from harness import journal
from harness.board import all_tasks, scan
from harness.clock import overdue
from harness.util import HarnessError, now, now_iso, parse_iso, sh, today, write_text

TARGETS = os.path.join(".harness", "targets.json")
ESCALATIONS = os.path.join(".harness", "escalations.md")

# Every stock, its unit, and the direction of a healthy value.
STOCKS = {
    "wip": ("tasks", "max"),
    "eye_queue": ("tasks", "max"),
    "eye_queue_age_days": ("days", "max"),
    "overdue_sprints": ("sprints", "max"),
    "backlog_size": ("tasks", "max"),
    "user_owned_open": ("tasks", "max"),
    "sessions_7d": ("sessions", "min"),
    "qa_closed_7d": ("verdicts", "min"),
    "commits_7d": ("commits", "min"),
    "days_since_session": ("days", "max"),
    "dirty_files": ("files", "max"),
    "front_stale_days": ("days", "max"),
}


# ---------------------------------------------------------------- targets

def read_targets(root):
    p = os.path.join(root, TARGETS)
    if not os.path.exists(p):
        return {"targets": {}}
    with open(p, encoding="utf-8") as fh:
        try:
            data = json.load(fh)
        except ValueError as exc:
            raise HarnessError("%s is not valid JSON: %s. Fix the file by hand, it is yours." % (TARGETS, exc))
    data.setdefault("targets", {})
    return data


def set_target(root, stock, value, by, why):
    """The only writer of targets.json. Every target records who, when, and why."""
    if stock not in STOCKS:
        raise HarnessError("unknown stock %s. Known: %s" % (stock, ", ".join(sorted(STOCKS))))
    if not by or not why:
        raise HarnessError("a target needs --by <who> and --why \"<text>\". A target without an author becomes the agent's target.")
    try:
        number = float(value)
        number = int(number) if number.is_integer() else number
    except ValueError:
        raise HarnessError("the value must be a number, not %r" % value)
    data = read_targets(root)
    data["targets"][stock] = {"value": number, "decided_by": by, "date": today().isoformat(), "why": why}
    data.setdefault("$comment", [
        "Targets. The USER declares them through `python3 -m harness target set`.",
        "The agent never writes this file. Current values are computed by `python3 -m harness state`.",
        "A stored current value rots in silence, and then a reader treats it as a measurement.",
    ])
    write_text(os.path.join(root, TARGETS), json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    return data["targets"][stock]


def wip_cap(root):
    t = read_targets(root)["targets"].get("wip")
    return int(t["value"]) if t else None


# ---------------------------------------------------------------- measurement

def _git(root, args, timeout=30):
    code, out = sh(["git"] + args, cwd=root, timeout=timeout)
    return out if code == 0 else None


def _commits_since_days(root, days):
    out = _git(root, ["rev-list", "--count", "--since=%d.days" % days, "HEAD"])
    if out is None or not out.strip().isdigit():
        return None, "git log is not available"
    return int(out.strip()), ""


def _dirty_files(root):
    out = _git(root, ["status", "--short"])
    if out is None:
        return None, "git status is not available"
    return len([l for l in out.splitlines() if l.strip()]), ""


def _entered_at(root, path):
    """When the file first appeared at this path, from the git history. None when uncommitted."""
    relpath = os.path.relpath(path, root)
    out = _git(root, ["log", "--format=%at", "--diff-filter=ACR", "--", relpath])
    if not out or not out.strip():
        return None
    stamps = [int(x) for x in out.split() if x.strip().isdigit()]
    return min(stamps) if stamps else None


def _front_stale(root):
    """Age in days of the oldest `touched` date on the front board. None when no row has one."""
    p = os.path.join(root, "docs", "ACTIVITY.md")
    if not os.path.exists(p):
        return None, "docs/ACTIVITY.md is missing"
    from harness.session import front_rows
    rows = front_rows(root)
    dates = [r.get("touched") for r in rows if r.get("touched")]
    if not dates:
        return None, "no row carries a touched date (%d rows)" % len(rows)
    oldest = min(dates)
    return (today() - oldest).days, ""


def measure(root):
    """Compute every stock. Return a list of dicts with current, target, gap, source."""
    tree = scan(root)
    tasks = all_tasks(tree)
    targets = read_targets(root)["targets"]
    rows = []

    def add(stock, current, source, reason=""):
        unit, direction = STOCKS[stock]
        t = targets.get(stock)
        target = t["value"] if t else None
        gap = None
        if current is not None and target is not None:
            gap = current - target if direction == "max" else target - current
        rows.append({
            "stock": stock, "unit": unit, "direction": direction,
            "current": current, "measured": current is not None, "reason": reason,
            "target": target, "decided_by": t["decided_by"] if t else None, "gap": gap,
            "over": (gap is not None and gap > 0), "source": source,
        })

    wip = [t for t in tasks if t.state == "in-progress"]
    add("wip", len(wip), "work/**/in-progress/")
    eye_q = [t for t in wip if t.needs_eye()]
    add("eye_queue", len(eye_q), "in-progress tasks with eye GLANCE or RUN")
    ages, missing = [], []
    for t in eye_q:
        at = _entered_at(root, t.path)
        if at is None:
            missing.append(t.id)
        else:
            ages.append((now().timestamp() - at) / 86400.0)
    if eye_q and not ages:
        add("eye_queue_age_days", None, "git log of the in-progress file",
            "the move of %s is not committed" % ", ".join(missing))
    elif eye_q:
        add("eye_queue_age_days", round(max(ages), 1), "git log of the in-progress file",
            ("uncommitted moves not counted: %s" % ", ".join(missing)) if missing else "")
    else:
        add("eye_queue_age_days", 0, "no task awaits a verdict")
    add("overdue_sprints", len(overdue(tree)), "sprint ends < today with open tasks")
    add("backlog_size", len(tree.backlog), "work/backlog/*.md")
    add("user_owned_open", sum(1 for t in tasks if t.owner == "user" and t.state != "done"), "owner: user, not done")

    sess = journal.sessions(root)
    cutoff = now() - _dt.timedelta(days=7)
    recent = []
    for s in sess:
        try:
            if parse_iso(s["ts"]) >= cutoff:
                recent.append(s)
        except (KeyError, ValueError):
            continue
    if os.path.exists(journal.path(root)):
        add("sessions_7d", len(recent), ".harness/journal.jsonl kind=session, last 7 days")
        add("qa_closed_7d", sum(len(s.get("qa_closed") or []) for s in recent), "journal qa_closed, last 7 days")
    else:
        add("sessions_7d", None, ".harness/journal.jsonl", "the journal does not exist yet")
        add("qa_closed_7d", None, ".harness/journal.jsonl", "the journal does not exist yet")
    c, why = _commits_since_days(root, 7)
    add("commits_7d", c, "git rev-list --since=7.days", why)
    last = journal.last_session(root)
    if last:
        try:
            add("days_since_session", round((now() - parse_iso(last["ts"])).total_seconds() / 86400.0, 1), "journal last session ts")
        except (KeyError, ValueError):
            add("days_since_session", None, "journal last session ts", "the last session line has no valid ts")
    else:
        add("days_since_session", None, "journal", "no session recorded yet")
    d, why = _dirty_files(root)
    add("dirty_files", d, "git status --short", why)
    f, why = _front_stale(root)
    add("front_stale_days", f, "docs/ACTIVITY.md column touched", why)
    return rows


def state_text(rows):
    lines = ["STATE — computed now, never stored.", "  %-22s %10s %8s %6s  %s" % ("stock", "current", "target", "gap", "source")]
    for r in rows:
        cur = "not measured" if r["current"] is None else str(r["current"])
        tgt = "—" if r["target"] is None else str(r["target"])
        gap = "" if r["gap"] is None else ("+%s" % r["gap"] if r["gap"] > 0 else str(r["gap"]))
        flag = " OVER" if r["over"] else ""
        note = ("  (%s)" % r["reason"]) if r["reason"] else ""
        lines.append("  %-22s %10s %8s %6s  %s%s%s" % (r["stock"], cur, tgt, gap, r["source"], note, flag))
    undeclared = [r["stock"] for r in rows if r["target"] is None]
    if undeclared:
        lines.append("  no target declared for: %s. The user declares one with `python3 -m harness target set <stock> <value> --by user --why \"...\"`." % ", ".join(undeclared))
    lines.append("  out of scope: whether the work was the right work. That is read, not counted.")
    return "\n".join(lines)


# ---------------------------------------------------------------- observations and escalations

def observe(root, rows=None):
    """Append one observation per stock over its target. Once per stock per day."""
    rows = rows if rows is not None else measure(root)
    day = now_iso()[:10]  # the same clock that stamps the journal line
    seen = {(o.get("stock"), str(o.get("ts", ""))[:10]) for o in journal.observations(root)}
    written = []
    for r in rows:
        if not r["over"] or (r["stock"], day) in seen:
            continue
        written.append(journal.append(root, {
            "kind": "observation", "stock": r["stock"], "current": r["current"],
            "target": r["target"], "gap": r["gap"], "decided_by": r["decided_by"],
        }))
    return written


def escalate(root, title, observed, level, decision_needed):
    """Append an escalation. The agent writes the observation. The user writes the decision."""
    p = os.path.join(root, ESCALATIONS)
    entry = (
        "\n## %s · %s\n\n**Observed, measured:** %s\n\n**Level:** %s\n\n"
        "**The decision that is needed, and it is the user's:** %s\n\n**Decision:** (empty until the user writes it)\n"
        % (today().isoformat(), title, observed, level, decision_needed)
    )
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(entry)
    return p
