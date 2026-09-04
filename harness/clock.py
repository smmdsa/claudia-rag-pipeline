"""The sprint clock. Dates are declared. Days are computed. Nothing is stored."""
from harness.util import parse_date, today


def sprint_dates(sprint):
    return parse_date(sprint.starts), parse_date(sprint.ends)


def days_remaining(sprint, on=None):
    """Days from `on` to the end of the sprint. Negative after the end. None without dates."""
    on = on or today()
    _, ends = sprint_dates(sprint)
    if ends is None:
        return None
    return (ends - on).days


def sprint_status(sprint, on=None):
    """One of: undated, future, active, ended."""
    on = on or today()
    starts, ends = sprint_dates(sprint)
    if starts is None or ends is None:
        return "undated"
    if on < starts:
        return "future"
    if on > ends:
        return "ended"
    return "active"


def open_tasks(sprint):
    return [t for e in sprint.epics for t in e.tasks if t.state != "done"]


def overdue(tree, on=None):
    """Sprints past their end date with open tasks. Each item: (sprint, open tasks)."""
    on = on or today()
    out = []
    for sp in tree.sprints:
        if sprint_status(sp, on) == "ended":
            left = open_tasks(sp)
            if left:
                out.append((sp, left))
    return out


def clock_report(tree, on=None):
    on = on or today()
    rows = []
    for sp in tree.sprints:
        rows.append({
            "sprint": sp.id,
            "title": sp.title,
            "starts": sp.starts or None,
            "ends": sp.ends or None,
            "status": sprint_status(sp, on),
            "days_remaining": days_remaining(sp, on),
            "open_tasks": len(open_tasks(sp)),
        })
    return {"today": on.isoformat(), "sprints": rows}


def clock_text(report):
    lines = ["Clock — today %s. Days are computed, never stored." % report["today"]]
    for r in report["sprints"]:
        if r["days_remaining"] is None:
            when = "no dates"
        elif r["status"] == "ended":
            when = "ended %d d ago" % (-r["days_remaining"])
        else:
            when = "%d d remain" % r["days_remaining"]
        flag = "  OVERDUE: %d open task(s)" % r["open_tasks"] if r["status"] == "ended" and r["open_tasks"] else ""
        lines.append("  %-12s %-8s %s .. %s  %s%s" % (r["sprint"], r["status"], r["starts"] or "?", r["ends"] or "?", when, flag))
    if not report["sprints"]:
        lines.append("  no sprint")
    return "\n".join(lines)
