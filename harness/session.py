"""The session pipeline: open, draft, close.

`open` prints one brief from measured data. `draft` writes the skeleton of the
session document with the measured fields filled. The agent writes the narrative.
`close` checks the document, updates the index, appends the journal line, and asks
the RAG stack to re-index. Both `open` and `close` run with no RAG stack.
"""
import glob
import os
import re
import time

from harness import board, journal, manifest, mcp, rag, scaffold, stack, state
from harness.board import next_tasks, scan, summary, waiting_decisions
from harness.clock import overdue
from harness.util import HarnessError, human_delta, now, parse_date, parse_iso, read_text, sh, write_text

SESSIONS = os.path.join("docs", "sessions")
LOG = os.path.join("docs", "session-log.md")
FRONT = os.path.join("docs", "ACTIVITY.md")
REQUIRED_SECTIONS = ("## TL;DR", "## What happened", "## Open items", "## How to resume")


# ---------------------------------------------------------------- the front board

def front_rows(root):
    """Rows of the front board table. Columns: front, owner, state, touched, next."""
    p = os.path.join(root, FRONT)
    if not os.path.exists(p):
        return []
    rows = []
    lines = read_text(p).splitlines()
    for i, line in enumerate(lines):
        if re.match(r"^##\s+Archive", line):
            break  # closed fronts are not live fronts
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if all(re.match(r"^:?-+:?$", c) for c in cells if c):
            continue  # the separator
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        if nxt.startswith("|") and all(re.match(r"^:?-+:?$", c.strip()) for c in nxt.strip().strip("|").split("|") if c.strip()):
            continue  # a header: the next line is its separator. Every table has one.
        if len(cells) < 3 or not cells[0]:
            continue
        if cells[0].startswith("(") and cells[0].endswith(")"):
            continue  # the placeholder row of the seeded file
        row = {"front": cells[0], "owner": cells[1] if len(cells) > 1 else "",
               "state": cells[2] if len(cells) > 2 else "", "touched": None, "next": ""}
        if len(cells) > 3:
            row["touched"] = parse_date(cells[3][:10])
            row["touched_raw"] = cells[3]
        if len(cells) > 4:
            row["next"] = cells[4]
        rows.append(row)
    return rows


# ---------------------------------------------------------------- open

def _git(root, args):
    code, out = sh(["git"] + args, cwd=root, timeout=30)
    return out.strip() if code == 0 else None


def last_session_doc(root):
    files = sorted(glob.glob(os.path.join(root, SESSIONS, "*.md")))
    return files[-1] if files else None


# After `docker compose start` a service needs a moment to answer. Three tries over
# fifteen seconds cover a warm start. A cold start is a build, and `start` never builds.
RETRY_SLEEP = 5
RETRIES = 3


def open_brief(root, with_rag=True, with_stack=True):
    brief = {"now": now().isoformat(timespec="seconds")}
    doc = manifest.doctor(root)
    if doc["state"] == "not-initialised":
        created = scaffold.init(root)
        brief["init"] = created
        doc = manifest.doctor(root)
    elif doc["state"] == "damaged" and manifest.only_missing_seeded(doc):
        brief["reseeded"] = scaffold.init(root)
        doc = manifest.doctor(root)
    brief["doctor"] = doc
    brief["rag"] = rag.health(root) if with_rag else {"level": "skipped", "problems": [], "warnings": []}
    if with_rag and with_stack and brief["rag"]["level"] == "broken":
        # The canary is the signal. Docker is the repair. A green canary costs no
        # docker call at all, so the common session never shells out.
        report = stack.start(root, "rag")
        brief["stack"] = report
        for _ in range(RETRIES if report.get("started") else 0):
            time.sleep(RETRY_SLEEP)
            brief["rag"] = rag.health(root)
            if brief["rag"]["level"] != "broken":
                break
    # The index answers on its port, and that does not prove that THIS agent can
    # search. Claude Code opens an MCP connection once, when its process starts.
    brief["mcp"] = (mcp.link_state(root) if with_rag and with_stack
                    else {"state": "unknown", "reason": "not measured", "gap": None,
                          "agent_started": None, "index_started": None})

    last = journal.last_session(root)
    brief["last_session"] = last
    brief["last_doc"] = os.path.relpath(last_session_doc(root), root) if last_session_doc(root) else None
    elapsed = None
    if last and last.get("ts"):
        try:
            elapsed = (now() - parse_iso(last["ts"])).total_seconds()
        except ValueError:
            elapsed = None
    brief["elapsed_seconds"] = elapsed
    brief["stale"] = bool(elapsed and elapsed > 30 * 86400)

    branch = _git(root, ["rev-parse", "--abbrev-ref", "HEAD"])
    head = _git(root, ["rev-parse", "--short", "HEAD"])
    dirty = _git(root, ["status", "--short"])
    git = {"available": branch is not None, "branch": branch, "head": head,
           "dirty_files": len([l for l in (dirty or "").splitlines() if l.strip()]) if dirty is not None else None,
           "commits_since_close": None, "branch_changed": None, "dirty_delta": None}
    if last and branch is not None:
        if last.get("head"):
            n = _git(root, ["rev-list", "--count", "%s..HEAD" % last["head"]])
            git["commits_since_close"] = int(n) if n and n.isdigit() else None
        git["branch_changed"] = (last.get("branch") != branch) if last.get("branch") else None
        if last.get("dirty") is not None and git["dirty_files"] is not None:
            git["dirty_delta"] = git["dirty_files"] - int(last["dirty"])
    brief["git"] = git

    rows = front_rows(root)
    brief["fronts"] = [{"n": i + 1, **r} for i, r in enumerate(rows)]

    tree = scan(root)
    errors, warnings = board.check(tree, wip_cap=state.wip_cap(root))
    users, agents = next_tasks(tree)
    brief["board"] = {
        "sprints": [{"id": sp.id, "title": sp.title, "ends": sp.ends or None,
                     "summary": summary([t for e in sp.epics for t in e.tasks])} for sp in tree.sprints],
        "backlog": len(tree.backlog),
        "in_progress": [board.task_dict(t, root) for t in board.all_tasks(tree) if t.state == "in-progress"],
        "user_tasks": [board.task_dict(t, root) for t in users],
        "next": board.task_dict(agents[0], root) if agents else None,
        "decisions": waiting_decisions(tree),
        "check_errors": errors, "check_warnings": warnings,
        "overdue": [{"sprint": sp.id, "open": len(left)} for sp, left in overdue(tree)],
    }
    rows = state.measure(root)
    brief["state_over"] = [r for r in rows if r["over"]]
    brief["state_unmeasured"] = [r["stock"] for r in rows if r["current"] is None]
    return brief


def open_text(b):
    lines = []
    if b.get("init"):
        lines.append("INIT: the repository was not initialised. init created %d file(s)." % len(b["init"]["created"]))
    if b.get("reseeded"):
        lines.append("RESEED: seeded file(s) were missing. init wrote %d again. "
                     "This repository keeps its own board out of git."
                     % len(b["reseeded"]["created"]))
    if b["doctor"]["state"] != "sound":
        lines.append(manifest.doctor_text(b["doctor"]))
    if b.get("stack"):
        line = stack.brief_line(b["stack"])
        if line:
            lines.append(line)
    if b["rag"]["level"] == "broken":
        lines.append("RAG: BROKEN — this session searches blind. " + "; ".join(b["rag"]["problems"]))
    elif b["rag"]["level"] == "warnings":
        lines.append("RAG: warnings — " + "; ".join(b["rag"]["warnings"]))
    link = mcp.link_line(b.get("mcp") or {})
    if link:
        lines.append(link)
    lines.append("")
    if b["last_session"]:
        lines.append("## Last session: %s" % b["last_session"].get("slug"))
        lines.append("Closed %s ago%s. Document: %s" % (human_delta(b["elapsed_seconds"]),
                                                       " — STALE, re-check its claims" if b["stale"] else "",
                                                       b["last_doc"] or "(none)"))
    else:
        lines.append("## Last session: none recorded. This is the first session with a journal.")
        lines.append("New here? Run `python3 -m harness help` for the map of what init created.")
    g = b["git"]
    lines.append("")
    lines.append("## Repository")
    if g["available"]:
        lines.append("- branch %s at %s%s" % (g["branch"], g["head"],
                                              " (CHANGED since the close)" if g["branch_changed"] else ""))
        if g["commits_since_close"] is not None:
            lines.append("- %d commit(s) since the close" % g["commits_since_close"])
        lines.append("- %d file(s) not committed%s" % (g["dirty_files"],
                                                       (" (%+d since the close)" % g["dirty_delta"]) if g["dirty_delta"] else ""))
    else:
        lines.append("- no git. Moves fall back to a rename and the history records nothing.")
    lines.append("")
    lines.append("## Fronts (docs/ACTIVITY.md)")
    if b["fronts"]:
        lines.append("| # | front | owner | state | touched | next |")
        lines.append("|---|---|---|---|---|---|")
        for r in b["fronts"]:
            lines.append("| #%d | %s | %s | %s | %s | %s |" % (r["n"], r["front"], r["owner"], r["state"],
                                                              r.get("touched_raw") or "", r["next"]))
        lines.append("Numbers are per brief. Name a front by its text in a later session.")
    else:
        lines.append("no rows. Add a row per live front in docs/ACTIVITY.md.")
    bd = b["board"]
    lines.append("")
    lines.append("## Board")
    for sp in bd["sprints"]:
        s = sp["summary"]
        lines.append("- %s — %s: %d/%d done · %d in progress · %d await a verdict · %d wait a decision"
                     % (sp["id"], sp["title"], s["done"], s["total"], s["in_progress"], s["awaiting_verdict"], s["wait_decision"]))
    lines.append("- backlog: %d task(s)" % bd["backlog"])
    for o in bd["overdue"]:
        lines.append("- OVERDUE: %s ended with %d open task(s)" % (o["sprint"], o["open"]))
    if bd["check_errors"]:
        lines.append("- CHECK RED: %d error(s). Fix the tree before new work." % len(bd["check_errors"]))
    for t in bd["in_progress"]:
        lines.append("- in progress: %s — %s%s" % (t["id"], t["title"], " (awaits verdict)" if t["eye"] != "NONE" else ""))
    for t in bd["user_tasks"]:
        lines.append("- ONLY THE USER: %s — %s%s" % (t["id"], t["title"], (" due %s" % t["due"]) if t["due"] else ""))
    if bd["next"]:
        lines.append("- NEXT: %s — %s (work %s, eye %s)" % (bd["next"]["id"], bd["next"]["title"], bd["next"]["work"], bd["next"]["eye"]))
    else:
        lines.append("- NEXT: nothing ready" + (". Decisions that block: %s" % ", ".join(bd["decisions"]) if bd["decisions"] else ""))
    if b["state_over"]:
        lines.append("")
        lines.append("## Targets missed")
        for r in b["state_over"]:
            lines.append("- %s is %s and the target is %s (set by %s)" % (r["stock"], r["current"], r["target"], r["decided_by"]))
    if b["state_unmeasured"]:
        lines.append("- not measured: %s" % ", ".join(b["state_unmeasured"]))
    lines.append("")
    lines.append("The suggestion comes from NEXT, or from the decision that blocks it. The user decides.")
    return "\n".join(lines)


# ---------------------------------------------------------------- draft and close

def slug_now():
    return now().strftime("%Y-%m-%d-%H%M")


def draft(root, slug=None):
    slug = slug or slug_now()
    p = os.path.join(root, SESSIONS, slug + ".md")
    if os.path.exists(p):
        raise HarnessError("%s exists. Read it before you write." % os.path.relpath(p, root))
    branch = _git(root, ["rev-parse", "--abbrev-ref", "HEAD"]) or "(no git)"
    status = _git(root, ["status", "--short"]) or ""
    last = journal.last_session(root)
    commits = ""
    if last and last.get("head"):
        commits = _git(root, ["log", "--oneline", "%s..HEAD" % last["head"]]) or ""
    text = (
        "# Session %s\n\n> **Closed:** %s\n> **Branch:** %s\n> **Commits in this session:** %s\n\n"
        "## TL;DR\n\n(one sentence)\n\n## What happened\n\n- (bullet with a commit hash or a file)\n\n"
        "## Decisions\n\n(why X and not Y. Quote the user when the words decided.)\n\n"
        "## Repository state at close\n\n```text\n%s\n```\n\n"
        "## Open items\n\n- (enough context for the next session)\n\n"
        "## References\n\n- (files, docs)\n\n## How to resume\n\n1. (step)\n"
        % (now().strftime("%Y-%m-%d %H:%M"), now().isoformat(timespec="seconds"), branch,
           commits.replace("\n", "; ") or "none", status or "(clean)")
    )
    write_text(p, text)
    return os.path.relpath(p, root)


def _section(text, header):
    m = re.search(r"^%s\s*\n(.*?)(?=^## |\Z)" % re.escape(header), text, re.M | re.S)
    return m.group(1).strip() if m else ""


def close(root, slug, qa_closed=(), qa_open=(), surprises=(), failed=(), reindex=True):
    p = os.path.join(root, SESSIONS, slug + ".md")
    if not os.path.exists(p):
        raise HarnessError("%s does not exist. Run `python3 -m harness session draft --slug %s` and write it." % (os.path.relpath(p, root), slug))
    text = read_text(p)
    missing = [h for h in REQUIRED_SECTIONS if not re.search(r"^%s\s*$" % re.escape(h), text, re.M)]
    if missing:
        raise HarnessError("%s lacks the section(s) %s." % (os.path.relpath(p, root), ", ".join(missing)))
    tldr = _section(text, "## TL;DR").splitlines()
    tldr = tldr[0].strip() if tldr else ""
    if not tldr or tldr.startswith("(one sentence"):
        raise HarnessError("the TL;DR of %s is empty. Write one sentence." % os.path.relpath(p, root))

    # The index: one row per session, newest first, under the table header.
    log_path = os.path.join(root, LOG)
    row = "| %s | [%s](sessions/%s.md) | %s |" % (now().strftime("%Y-%m-%d %H:%M"), slug, slug, tldr.replace("|", "/"))
    if os.path.exists(log_path):
        lines = read_text(log_path).splitlines()
        idx = None
        for i, line in enumerate(lines):
            if re.match(r"^\|\s*-+", line):
                idx = i + 1
                break
        if idx is None:
            lines += ["", "| date | session | TL;DR |", "|---|---|---|"]
            idx = len(lines)
        lines.insert(idx, row)
        write_text(log_path, "\n".join(lines) + "\n")
    else:
        write_text(log_path, "# Session log\n\nOne row per session. Newest first.\n\n| date | session | TL;DR |\n|---|---|---|\n%s\n" % row)

    branch = _git(root, ["rev-parse", "--abbrev-ref", "HEAD"])
    head = _git(root, ["rev-parse", "--short", "HEAD"])
    dirty = _git(root, ["status", "--short"])
    last = journal.last_session(root)
    commits = None
    if last and last.get("head") and head:
        n = _git(root, ["rev-list", "--count", "%s..HEAD" % last["head"]])
        commits = int(n) if n and n.isdigit() else None
    closed = []
    for item in qa_closed:
        # TASK-0007=ok:run  ->  {"id": "TASK-0007", "verdict": "ok", "how": "run"}
        m = re.match(r"^([^=]+)=([^:]+)(?::(.+))?$", item)
        if not m:
            raise HarnessError("--qa-closed takes ID=verdict[:how], not %r" % item)
        closed.append({"id": m.group(1).strip(), "verdict": m.group(2).strip(), "how": (m.group(3) or "").strip()})
    line = journal.append(root, {
        "kind": "session", "slug": slug, "branch": branch, "head": head, "commits": commits,
        "dirty": len([l for l in (dirty or "").splitlines() if l.strip()]) if dirty is not None else None,
        "qa_closed": closed, "qa_open": list(qa_open), "surprises": list(surprises), "failed": list(failed),
    })
    observations = state.observe(root)
    rag_result = rag.request_update(root) if reindex else {"ok": None, "note": "skipped"}
    tree = scan(root)
    s = summary(board.all_tasks(tree))
    return {"doc": os.path.relpath(p, root), "log": LOG, "journal": line, "observations": len(observations),
            "rag": rag_result, "awaiting_verdict": s["awaiting_verdict"], "qa_closed": len(closed)}


def close_text(r):
    lines = ["Session closed.",
             "- document: %s" % r["doc"],
             "- index: %s updated" % r["log"],
             "- journal: one session line appended (%d verdict(s) closed, %d observation(s))" % (r["qa_closed"], r["observations"]),
             "- eye queue: %d task(s) still await a verdict" % r["awaiting_verdict"]]
    rg = r["rag"]
    if rg.get("ok") is None:
        lines.append("- RAG: not re-indexed (%s)" % rg.get("note"))
    elif rg.get("ok"):
        # The note carries the outcome. A timeout says "started" and names `rag health`.
        lines.append("- RAG: re-index %s" % (rg.get("note") or "requested"))
    else:
        lines.append("- RAG: re-index FAILED (%s)" % rg.get("note"))
    lines.append("- memory: update the durable memory by hand when the session produced a lesson")
    return "\n".join(lines)
