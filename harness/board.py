"""The work board. The folder tree is the truth. This module stores nothing.

Layout:
  work/backlog/TASK-NNNN-slug.md                                   no sprint
  work/sprints/sprint-NNN/sprint-NNN.md                             starts, ends, goal
  work/sprints/sprint-NNN/epic-NN-slug/epic-NN-slug.md              goal, verdicts
  work/sprints/sprint-NNN/epic-NN-slug/{todo,in-progress,done}/TASK-NNNN-slug.md

Every command scans the tree again. A stored number rots in silence, and then a
reader treats it as a measurement. Source B measured that failure four times.
"""
import os
import re
from dataclasses import dataclass, field

from harness import frontmatter as fm
from harness.util import HarnessError, parse_date, read_text, rel, sh, today, write_text

STATES = ("todo", "in-progress", "done")
WORK = ("XS", "S", "M", "L", "XL")
EYE = ("NONE", "GLANCE", "RUN")
OWNER = ("agent", "user")
TASK_ID = re.compile(r"^TASK-\d{4}$")
DEFAULT_WIP_CAP = 3


@dataclass
class Task:
    id: str
    title: str
    work: str
    eye: str
    owner: str
    due: str
    priority: int
    priority_by: str
    priority_date: str
    priority_why: str
    blocked_by: list
    decision: str
    refs: list
    state: str
    path: str
    sprint: str = ""
    epic: str = ""
    epic_order: int = 0
    sprint_order: int = 0
    fields: dict = field(default_factory=dict)
    body: str = ""

    def has_verdict(self):
        return re.search(r"^## Verdict\s*$", self.body, re.M) is not None

    def needs_eye(self):
        return self.eye != "NONE"

    def priority_provenance_error(self):
        """The error text when `priority` has no author, no date, or the agent as author. Else ''."""
        if not self.priority:
            return ""
        if not self.priority_by or not self.priority_date:
            return ("%s carries priority %d with no author or no date. A priority without provenance is an "
                    "opinion. Set it with `python3 -m harness priority %s --by user --why \"...\"`, or remove it "
                    "with `python3 -m harness priority %s --clear`." % (self.id, self.priority, self.id, self.id))
        if self.priority_by.strip().lower() == "agent":
            return ("%s carries a priority that the agent set. The user names the next thing, never the agent. "
                    "Run `python3 -m harness priority %s --by user --why \"...\"`, or `--clear`." % (self.id, self.id))
        if parse_date(self.priority_date) is None:
            return ("%s carries priority-date %r, and it is not YYYY-MM-DD. Run `python3 -m harness priority %s "
                    "--by user --why \"...\"` to record it again." % (self.id, self.priority_date, self.id))
        return ""


@dataclass
class Epic:
    id: str
    title: str
    dir: str
    path: str
    sheet: str
    order: int
    tasks: list = field(default_factory=list)
    fields: dict = field(default_factory=dict)


@dataclass
class Sprint:
    id: str
    title: str
    dir: str
    path: str
    sheet: str
    order: int
    starts: str = ""
    ends: str = ""
    epics: list = field(default_factory=list)
    fields: dict = field(default_factory=dict)


@dataclass
class Tree:
    root: str
    sprints: list = field(default_factory=list)
    backlog: list = field(default_factory=list)


# ---------------------------------------------------------------- scan

def work_dir(root):
    return os.path.join(root, "work")


def _dirs(path):
    if not os.path.isdir(path):
        return []
    return sorted(d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d)))


def _order(name):
    m = re.search(r"(\d+)", name)
    return int(m.group(1)) if m else 0


def _read_task(path, state):
    text = read_text(path)
    fields, body = fm.parse(text)
    name = os.path.basename(path)[:-3]
    return Task(
        id=str(fields.get("id") or "-".join(name.split("-")[:2])),
        title=str(fields.get("title") or "(no title)"),
        work=str(fields.get("work") or "?").upper(),
        eye=str(fields.get("eye") or "?").upper(),
        owner=str(fields.get("owner") or "agent").lower(),
        due=str(fields.get("due") or ""),
        priority=int(fields.get("priority") or 0) if str(fields.get("priority") or "0").isdigit() else 0,
        priority_by=str(fields.get("priority-by") or ""),
        priority_date=str(fields.get("priority-date") or ""),
        priority_why=str(fields.get("priority-why") or ""),
        blocked_by=fm.as_list(fields.get("blocked-by")),
        decision=str(fields.get("needs-decision") or ""),
        refs=fm.as_list(fields.get("refs")),
        state=state,
        path=path,
        fields=fields,
        body=body,
    )


def _task_files(folder):
    if not os.path.isdir(folder):
        return []
    return sorted(f for f in os.listdir(folder) if f.endswith(".md") and f.startswith("TASK-"))


def scan(root):
    """Read the whole tree. This is the only reader. Every command calls it."""
    tree = Tree(root=root)
    sprints_dir = os.path.join(work_dir(root), "sprints")
    for sd in _dirs(sprints_dir):
        if not re.match(r"^sprint-\d+$", sd):
            continue
        sdir = os.path.join(sprints_dir, sd)
        sheet = os.path.join(sdir, sd + ".md")
        sfields = fm.read(sheet)[0] if os.path.exists(sheet) else {}
        sp = Sprint(
            id=str(sfields.get("id") or sd), title=str(sfields.get("title") or sd), dir=sd,
            path=sdir, sheet=sheet, order=_order(sd),
            starts=str(sfields.get("starts") or ""), ends=str(sfields.get("ends") or ""), fields=sfields,
        )
        for ed in _dirs(sdir):
            if not ed.startswith("epic-"):
                continue
            edir = os.path.join(sdir, ed)
            esheet = os.path.join(edir, ed + ".md")
            efields = fm.read(esheet)[0] if os.path.exists(esheet) else {}
            ep = Epic(id=str(efields.get("id") or ed), title=str(efields.get("title") or ed), dir=ed,
                      path=edir, sheet=esheet, order=_order(ed), fields=efields)
            for st in STATES:
                for f in _task_files(os.path.join(edir, st)):
                    t = _read_task(os.path.join(edir, st, f), st)
                    t.sprint, t.epic, t.epic_order, t.sprint_order = sp.id, ep.id, ep.order, sp.order
                    ep.tasks.append(t)
            sp.epics.append(ep)
        tree.sprints.append(sp)
    backlog = os.path.join(work_dir(root), "backlog")
    for f in _task_files(backlog):
        t = _read_task(os.path.join(backlog, f), "todo")
        t.sprint_order = 10 ** 6  # the backlog ranks after every sprint
        tree.backlog.append(t)
    return tree


def all_tasks(tree):
    return [t for sp in tree.sprints for e in sp.epics for t in e.tasks] + list(tree.backlog)


def find(tree, task_id):
    wanted = str(task_id).upper()
    for t in all_tasks(tree):
        if t.id.upper() == wanted:
            return t
    return None


def find_epic(tree, epic_id, sprint=None):
    """Find one epic. `sprint` limits the search to one sprint.

    An epic id is unique inside its sprint, and not across sprints: every sprint
    starts at EP-01. Without `sprint`, two sprints answer to the same id, and this
    function raises and names every candidate. It never picks the first one. A caller
    that already knows the sprint of a task must pass it: a silent first match writes
    the verdict of one sprint into the epic sheet of another.

    The folder name always identifies one epic.
    """
    hits = []
    for sp in tree.sprints:
        if sprint and sp.id != sprint and sp.dir != sprint:
            continue
        for e in sp.epics:
            if e.id.upper() == str(epic_id).upper() or e.dir == epic_id:
                hits.append((sp, e))
    if not hits:
        return None, None
    if len(hits) > 1:
        raise HarnessError(
            "%s names %d epics, one per sprint: %s. An epic id repeats across sprints. "
            "Pass the folder name instead." % (
                epic_id, len(hits), ", ".join("%s/%s" % (sp.id, e.dir) for sp, e in hits)))
    return hits[0]


def find_sprint(tree, sprint_id):
    for sp in tree.sprints:
        if sp.id == sprint_id or sp.dir == sprint_id:
            return sp
    return None


# ---------------------------------------------------------------- ready and next

def ready(task, tree):
    """A task is ready in `todo`, with every blocker done and no open decision."""
    if task.state != "todo":
        return False
    if task.decision:
        return False
    for b in task.blocked_by:
        d = find(tree, b)
        if d is None or d.state != "done":
            return False
    return True


def why_not_ready(task, tree):
    if task.decision:
        return "waits decision %s" % task.decision
    open_blockers = [b for b in task.blocked_by if (find(tree, b) is None or find(tree, b).state != "done")]
    if open_blockers:
        return "after %s" % ", ".join(open_blockers)
    return ""


def rank_key(task):
    """Deadline first, then the user's priority, then sprint, epic, and id."""
    due = parse_date(task.due)
    return (
        0 if due else 1,
        due.toordinal() if due else 0,
        0 if task.priority == 1 else 1,
        task.sprint_order,
        task.epic_order,
        task.id,
    )


def next_tasks(tree):
    """Return (tasks only the user can do, ranked agent tasks)."""
    ready_list = [t for t in all_tasks(tree) if ready(t, tree)]
    users = sorted((t for t in ready_list if t.owner == "user"), key=rank_key)
    agents = sorted((t for t in ready_list if t.owner != "user"), key=rank_key)
    return users, agents


def waiting_decisions(tree):
    return sorted({t.decision for t in all_tasks(tree) if t.decision and t.state != "done"})


# ---------------------------------------------------------------- summaries

def task_dict(t, root):
    return {
        "id": t.id, "title": t.title, "work": t.work, "eye": t.eye, "owner": t.owner,
        "due": t.due or None, "priority": t.priority, "priority_by": t.priority_by or None,
        "priority_date": t.priority_date or None, "blocked_by": t.blocked_by,
        "needs_decision": t.decision or None, "refs": t.refs, "state": t.state,
        "sprint": t.sprint or None, "epic": t.epic or None, "path": rel(root, t.path),
        "has_verdict": t.has_verdict(),
    }


def summary(tasks):
    """Counts that every view uses. Computed on each call."""
    open_tasks = [t for t in tasks if t.state != "done"]
    return {
        "total": len(tasks),
        "done": sum(1 for t in tasks if t.state == "done"),
        "in_progress": sum(1 for t in tasks if t.state == "in-progress"),
        "todo": sum(1 for t in tasks if t.state == "todo"),
        "need_eye": sum(1 for t in open_tasks if t.needs_eye()),
        "awaiting_verdict": sum(1 for t in tasks if t.state == "in-progress" and t.needs_eye()),
        "wait_decision": sum(1 for t in open_tasks if t.decision),
        "user_owned_open": sum(1 for t in open_tasks if t.owner == "user"),
        "with_due": sorted({t.due for t in open_tasks if t.due}),
    }


def tree_dict(tree):
    from harness.clock import days_remaining, sprint_status  # local import: clock imports util only
    root = tree.root
    return {
        "computed": True,
        "sprints": [{
            "id": sp.id, "title": sp.title, "dir": sp.dir, "starts": sp.starts or None, "ends": sp.ends or None,
            "status": sprint_status(sp), "days_remaining": days_remaining(sp),
            "summary": summary([t for e in sp.epics for t in e.tasks]),
            "epics": [{
                "id": e.id, "title": e.title, "dir": e.dir, "summary": summary(e.tasks),
                "tasks": [task_dict(t, root) for t in e.tasks],
            } for e in sp.epics],
        } for sp in tree.sprints],
        "backlog": [task_dict(t, root) for t in tree.backlog],
    }


def _line(t, tree):
    mark = {"done": "[x]", "in-progress": "[~]"}.get(t.state) or ("[ ]" if ready(t, tree) else "[-]")
    extra = []
    if t.owner == "user":
        extra.append("@user")
    if t.due:
        extra.append("due " + t.due)
    if t.priority == 1:
        extra.append("priority 1 by %s" % (t.priority_by or "NOBODY"))
    if t.state == "in-progress" and t.needs_eye():
        extra.append("awaits verdict")
    why = why_not_ready(t, tree) if t.state == "todo" else ""
    if why:
        extra.append(why)
    return "  %s %-10s %-8s %s%s" % (mark, t.id, "%s/%s" % (t.work, t.eye), t.title,
                                     ("  (" + " · ".join(extra) + ")") if extra else "")


def board_text(tree):
    from harness.clock import days_remaining, sprint_status
    lines = ["BOARD — computed from the folder tree on %s. Nothing here is stored." % today().isoformat()]
    for sp in tree.sprints:
        s = summary([t for e in sp.epics for t in e.tasks])
        status = sprint_status(sp)
        left = days_remaining(sp)
        when = "no dates" if left is None else ("%d d remain" % left if left >= 0 else "ended %d d ago" % -left)
        lines.append("")
        lines.append("%s — %s   [%s · %s]" % (sp.id, sp.title, status, when))
        lines.append("  %d/%d done · %d in progress · %d need an eye · %d await a verdict · %d wait a decision"
                     % (s["done"], s["total"], s["in_progress"], s["need_eye"], s["awaiting_verdict"], s["wait_decision"]))
        if s["user_owned_open"] or s["with_due"]:
            lines.append("  %d task(s) only the user can do · deadlines: %s"
                         % (s["user_owned_open"], ", ".join(s["with_due"]) or "none"))
        if status == "ended" and s["total"] - s["done"]:
            lines.append("  OVERDUE: the sprint ended on %s with %d open task(s). The date does not move." % (sp.ends, s["total"] - s["done"]))
        for e in sp.epics:
            es = summary(e.tasks)
            lines.append("")
            lines.append("  %s %s (%d/%d)" % (e.id, e.title, es["done"], es["total"]))
            for t in e.tasks:
                lines.append(_line(t, tree))
    if tree.backlog:
        lines.append("")
        lines.append("BACKLOG (%d task(s), no sprint)" % len(tree.backlog))
        for t in tree.backlog:
            lines.append(_line(t, tree))
    users, agents = next_tasks(tree)
    lines.append("")
    if users:
        lines.append("ONLY THE USER CAN DO: " + ", ".join(t.id for t in users))
    lines.append("NEXT: " + ("%s — %s" % (agents[0].id, agents[0].title) if agents else "nothing ready"))
    if not agents:
        d = waiting_decisions(tree)
        if d:
            lines.append("  decisions that block work: " + ", ".join(d))
    return "\n".join(lines)


def next_text(tree, root):
    users, agents = next_tasks(tree)
    lines = []
    if users:
        lines.append("%d task(s) wait on the user. Nobody else can do them:" % len(users))
        for t in users:
            lines.append("  %s — %s%s" % (t.id, t.title, (" (due %s)" % t.due) if t.due else ""))
    if not agents:
        lines.append("Nothing is ready for the agent.")
        d = waiting_decisions(tree)
        if d:
            lines.append("  %d decision(s) block work: %s" % (len(d), ", ".join(d)))
        return "\n".join(lines)
    t = agents[0]
    lines.append("%s — %s" % (t.id, t.title))
    lines.append("  %s · work %s · eye %s · %s" % (t.epic or "backlog", t.work, t.eye, rel(root, t.path)))
    lines.append("  Start it: python3 -m harness start %s" % t.id)
    return "\n".join(lines)


def filter_tasks(tree, sprint=None, epic=None, state=None, owner=None):
    out = []
    for t in all_tasks(tree):
        if sprint and t.sprint != sprint and not (sprint == "backlog" and not t.sprint):
            continue
        if epic and t.epic.upper() != epic.upper():
            continue
        if state and t.state != state:
            continue
        if owner and t.owner != owner:
            continue
        out.append(t)
    return out


# ---------------------------------------------------------------- check

def check(tree, wip_cap=None):
    """Measure the SHAPE of the tree. Return (errors, warnings).

    This never measures whether a task is correct, whether a size is honest, or
    whether a done task works. A person closes a task, not this function.
    """
    errors, warnings = [], []
    seen = {}
    cap = wip_cap if wip_cap is not None else DEFAULT_WIP_CAP
    if not tree.sprints and not tree.backlog:
        warnings.append("no sprint and no backlog task under work/")
    for sp in tree.sprints:
        if not os.path.exists(sp.sheet):
            errors.append("%s: the sprint sheet %s.md is missing" % (sp.dir, sp.dir))
        starts, ends = parse_date(sp.starts), parse_date(sp.ends)
        if sp.starts and starts is None:
            errors.append("%s: starts is %r. Use YYYY-MM-DD." % (sp.id, sp.starts))
        if sp.ends and ends is None:
            errors.append("%s: ends is %r. Use YYYY-MM-DD." % (sp.id, sp.ends))
        if starts and ends and ends < starts:
            errors.append("%s: ends %s is before starts %s" % (sp.id, sp.ends, sp.starts))
        if not (starts and ends):
            warnings.append("%s: the sprint has no starts or no ends. The clock cannot run." % sp.id)
        if not sp.epics:
            warnings.append("%s: the sprint has no epic" % sp.id)
        if ends and today() > ends:
            left = [t for e in sp.epics for t in e.tasks if t.state != "done"]
            if left:
                warnings.append("%s: ended on %s with %d open task(s). Run `ceremony review`." % (sp.id, sp.ends, len(left)))
        for e in sp.epics:
            if not os.path.exists(e.sheet):
                errors.append("%s: the epic sheet %s.md is missing" % (e.dir, e.dir))
            for st in STATES:
                if not os.path.isdir(os.path.join(e.path, st)):
                    warnings.append("%s: the folder %s/ is missing" % (e.dir, st))
    for t in all_tasks(tree):
        if t.id in seen:
            errors.append("%s: the id is used twice (%s and %s)" % (t.id, rel(tree.root, seen[t.id]), rel(tree.root, t.path)))
        seen[t.id] = t.path
        if not TASK_ID.match(t.id):
            errors.append("%s: the id must match TASK-NNNN (%s)" % (t.id, rel(tree.root, t.path)))
        if t.work not in WORK:
            errors.append("%s: work is %r. Use one of %s." % (t.id, t.work, " ".join(WORK)))
        if t.eye not in EYE:
            errors.append("%s: eye is %r. Use one of %s." % (t.id, t.eye, " ".join(EYE)))
        if t.owner not in OWNER:
            errors.append("%s: owner is %r. Use one of %s." % (t.id, t.owner, " ".join(OWNER)))
        if t.due and parse_date(t.due) is None:
            errors.append("%s: due is %r. Use YYYY-MM-DD." % (t.id, t.due))
        if not os.path.basename(t.path).startswith(t.id + "-") and os.path.basename(t.path) != t.id + ".md":
            warnings.append("%s: the file name does not start with the id (%s)" % (t.id, rel(tree.root, t.path)))
        if t.work == "XL" and t.state != "done":
            warnings.append("%s: work is XL. Split it. An XL task is a task that nobody scoped." % t.id)
        if t.state == "done" and t.needs_eye() and not t.has_verdict():
            errors.append("%s: is done with eye %s and has no `## Verdict` section. A person closes it." % (t.id, t.eye))
        if t.state == "done" and t.decision:
            errors.append("%s: is done and still names needs-decision %s" % (t.id, t.decision))
        # Law 8: a priority the agent assigns turns `next` into an opinion. Provenance, or nothing.
        provenance = t.priority_provenance_error()
        if provenance:
            errors.append(provenance)
        for b in t.blocked_by:
            d = find(tree, b)
            if d is None:
                errors.append("%s: blocked-by names %s, and no task has that id" % (t.id, b))
            elif t.state == "done" and d.state != "done":
                errors.append("%s is done, and its blocker %s is not" % (t.id, b))
    wip = [t for t in all_tasks(tree) if t.state == "in-progress"]
    if len(wip) > cap:
        warnings.append("%d tasks are in progress at once, and the cap is %d. Finish work before you start more."
                        % (len(wip), cap))
    return errors, warnings


def check_text(errors, warnings, n_tasks):
    lines = []
    for w in warnings:
        lines.append("  warn  " + w)
    for e in errors:
        lines.append("  error " + e)
    if errors:
        lines.append("RED — %d error(s), %d warning(s)" % (len(errors), len(warnings)))
    else:
        lines.append("GREEN — %d task(s), 0 errors, %d warning(s)" % (n_tasks, len(warnings)))
    lines.append("scope: check measures the SHAPE of the tree. It never measures whether a task is correct.")
    return "\n".join(lines)


# ---------------------------------------------------------------- moves

def _git_mv(root, src, dst):
    """Move with git so the history records the move. Fall back to a rename."""
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    code, out = sh(["git", "mv", src, dst], cwd=root, timeout=30)
    if code == 0:
        return "git mv"
    os.replace(src, dst)
    return "rename (git mv failed: %s)" % out.strip().splitlines()[-1] if out.strip() else "rename (no git)"


def _append_section(path, header, line):
    """Write the line at the end of the SECTION, and never at the end of the file.

    A sheet holds `## Verdicts` above `## Out of scope`. The end of the file is not the
    end of the section, so an append to the file writes the verdict under the wrong
    header. The section ends at the next `## ` line, or at the end of the text.
    A deeper header, such as `### 2026`, belongs to the section and never ends it.
    """
    text = read_text(path) if os.path.exists(path) else ""
    found = re.search(r"^%s\s*$" % re.escape(header), text, re.M)
    if found is None:
        write_text(path, text.rstrip("\n") + "\n\n" + header + "\n\n" + line + "\n")
        return
    after = re.search(r"^## ", text[found.end():], re.M)
    cut = found.end() + after.start() if after else len(text)
    head = text[:cut].rstrip("\n") + "\n" + line + "\n"
    tail = text[cut:]
    write_text(path, head + "\n" + tail if tail else head)


def move(root, tree, task_id, to, verdict=None, by=None):
    """Move one task between state folders. Return a report dict."""
    t = find(tree, task_id)
    if t is None:
        raise HarnessError("no task with id %s. Run `python3 -m harness list` to see the ids." % task_id)
    if not t.sprint:
        raise HarnessError("%s is in the backlog. Move it into an epic first: `python3 -m harness assign %s --epic EP-NN`." % (t.id, t.id))
    if to not in STATES:
        raise HarnessError("unknown state %s" % to)
    if t.state == to:
        raise HarnessError("%s is already in %s." % (t.id, to))
    allowed = {"in-progress": ("todo",), "done": ("in-progress",), "todo": ("in-progress",)}
    if t.state not in allowed[to]:
        raise HarnessError("%s is in %s. A move to %s starts from %s." % (t.id, t.state, to, " or ".join(allowed[to])))
    if to == "in-progress" and t.decision:
        raise HarnessError("%s waits decision %s. The user decides, then the task starts." % (t.id, t.decision))
    if to == "in-progress" and not ready(t, tree):
        raise HarnessError("%s is not ready: %s." % (t.id, why_not_ready(t, tree)))
    if to == "done" and t.needs_eye():
        if not verdict:
            raise HarnessError(
                "%s has eye %s. It does not close without a human verdict. "
                "Pass the user's words: --verdict \"<words>\" --by user. Compiling green is not working."
                % (t.id, t.eye))
        _append_section(t.path, "## Verdict", "- %s · by %s · \"%s\"" % (today().isoformat(), by or "user", verdict))
        _, ep = find_epic(tree, t.epic, sprint=t.sprint)
        if ep and os.path.exists(ep.sheet):
            _append_section(ep.sheet, "## Verdicts", "- %s · %s · \"%s\"" % (today().isoformat(), t.id, verdict))
    dst = os.path.join(os.path.dirname(os.path.dirname(t.path)), to, os.path.basename(t.path))
    how = _git_mv(root, t.path, dst)
    note = ""
    if to == "in-progress" and t.needs_eye():
        note = "this task needs an eye (%s). It cannot close without a human verdict." % t.eye
    return {"id": t.id, "from": t.state, "to": to, "how": how, "path": rel(root, dst), "note": note}


PRIORITY_FIELDS = ("priority", "priority-by", "priority-date", "priority-why")


def set_priority(root, tree, task_id, by=None, why=None, clear=False):
    """The only writer of `priority`. It records the value, the author, the date, and the reason.

    The agent cannot name itself as the author. The pre-write hook denies the hand edit.
    """
    t = find(tree, task_id)
    if t is None:
        raise HarnessError("no task with id %s" % task_id)
    fields, body = fm.read(t.path)
    kept = {k: v for k, v in fields.items() if k not in PRIORITY_FIELDS}
    if clear:
        write_text(t.path, fm.dump(kept, body))
        return {"id": t.id, "priority": 0, "path": rel(root, t.path)}
    if not by or not why:
        raise HarnessError("a priority needs --by <who> and --why \"<the user's words>\". "
                           "A priority without an author becomes the agent's priority.")
    if by.strip().lower() == "agent":
        raise HarnessError("the agent cannot set a priority. It is set from what the user SAID. Pass --by user.")
    stamp = {"priority": 1, "priority-by": by.strip(), "priority-date": today().isoformat(), "priority-why": why.strip()}
    # Keep the front matter readable: the priority block sits after `due`, or after `owner`.
    anchor = "due" if "due" in kept else "owner"
    ordered = {}
    for key, value in kept.items():
        ordered[key] = value
        if key == anchor:
            ordered.update(stamp)
    if "priority" not in ordered:
        ordered.update(stamp)
    write_text(t.path, fm.dump(ordered, body))
    return {"id": t.id, "priority": 1, "by": stamp["priority-by"], "date": stamp["priority-date"], "path": rel(root, t.path)}


def assign(root, tree, task_id, epic_id):
    """Move a backlog task into the todo folder of an epic."""
    t = find(tree, task_id)
    if t is None:
        raise HarnessError("no task with id %s" % task_id)
    if t.sprint:
        raise HarnessError("%s already belongs to %s. Only backlog tasks are assigned." % (t.id, t.epic))
    _, ep = find_epic(tree, epic_id)
    if ep is None:
        raise HarnessError("no epic with id %s" % epic_id)
    dst = os.path.join(ep.path, "todo", os.path.basename(t.path))
    how = _git_mv(root, t.path, dst)
    return {"id": t.id, "epic": ep.id, "how": how, "path": rel(root, dst)}


# ---------------------------------------------------------------- new

def slugify(text):
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:60] or "task"


def next_task_id(tree):
    top = 0
    for t in all_tasks(tree):
        m = re.match(r"^TASK-(\d{4})$", t.id)
        if m:
            top = max(top, int(m.group(1)))
    return "TASK-%04d" % (top + 1)


def next_epic_dir(sprint):
    top = max([e.order for e in sprint.epics] + [0])
    return top + 1


SPRINT_ID = re.compile(r"^sprint-\d{3}$")


def next_sprint_dir(tree):
    top = max([sp.order for sp in tree.sprints] + [0])
    return "sprint-%03d" % (top + 1)


def template_text(root, name):
    path = os.path.join(work_dir(root), "templates", name + ".md")
    if not os.path.exists(path):
        raise HarnessError("the template %s is missing. Run `python3 -m harness doctor`." % rel(root, path))
    return read_text(path)


def new_task(root, tree, title, epic=None, work="S", eye="NONE", owner="agent", due="",
             blocked_by=(), decision="", refs=()):
    if work.upper() not in WORK:
        raise HarnessError("work is %r. Use one of %s." % (work, " ".join(WORK)))
    if eye.upper() not in EYE:
        raise HarnessError("eye is %r. Use one of %s." % (eye, " ".join(EYE)))
    if owner not in OWNER:
        raise HarnessError("owner is %r. Use one of %s." % (owner, " ".join(OWNER)))
    if due and parse_date(due) is None:
        raise HarnessError("due is %r. Use YYYY-MM-DD." % due)
    task_id = next_task_id(tree)
    if epic:
        _, ep = find_epic(tree, epic)
        if ep is None:
            raise HarnessError("no epic with id %s" % epic)
        folder = os.path.join(ep.path, "todo")
        epic_id = ep.id
    else:
        folder = os.path.join(work_dir(root), "backlog")
        epic_id = ""
    fields = {"id": task_id, "title": title}
    if epic_id:
        fields["epic"] = epic_id
    fields.update({"work": work.upper(), "eye": eye.upper(), "owner": owner})
    if due:
        fields["due"] = due
    # No `priority` here. `set_priority` is the only writer, and it records the author.
    if blocked_by:
        fields["blocked-by"] = list(blocked_by)
    if decision:
        fields["needs-decision"] = decision
    if refs:
        fields["refs"] = list(refs)
    _, body = fm.parse(template_text(root, "task"))
    body = body.replace("{{ID}}", task_id).replace("{{TITLE}}", title)
    path = os.path.join(folder, "%s-%s.md" % (task_id, slugify(title)))
    write_text(path, fm.dump(fields, body))
    return {"id": task_id, "path": rel(root, path), "epic": epic_id or None}


def new_epic(root, tree, sprint_id, title, work="M", eye="GLANCE"):
    sp = find_sprint(tree, sprint_id)
    if sp is None:
        raise HarnessError("no sprint with id %s" % sprint_id)
    n = next_epic_dir(sp)
    epic_id = "EP-%02d" % n
    edir = os.path.join(sp.path, "epic-%02d-%s" % (n, slugify(title)))
    fields = {"id": epic_id, "title": title, "sprint": sp.id, "work": work.upper(), "eye": eye.upper()}
    _, body = fm.parse(template_text(root, "epic"))
    body = body.replace("{{ID}}", epic_id).replace("{{TITLE}}", title)
    sheet = os.path.join(edir, os.path.basename(edir) + ".md")
    write_text(sheet, fm.dump(fields, body))
    for st in STATES:
        os.makedirs(os.path.join(edir, st), exist_ok=True)
        write_text(os.path.join(edir, st, ".gitkeep"), "")
    return {"id": epic_id, "path": rel(root, sheet)}


def new_sprint(root, tree, title, starts, ends, goal="", sprint_id=None):
    """Create a sprint. Without `sprint_id` the tool numbers it after the last one.

    `sprint_id` names a sprint that the counter cannot reach. `next_sprint_dir` counts
    up from the highest sprint, so it never writes `sprint-000`. A repository that
    wants a sprint zero for its setup needs the name, not the count.
    """
    if parse_date(starts) is None or parse_date(ends) is None:
        raise HarnessError("starts and ends must be YYYY-MM-DD dates.")
    if parse_date(ends) < parse_date(starts):
        raise HarnessError("ends %s is before starts %s." % (ends, starts))
    if sprint_id is None:
        sd = next_sprint_dir(tree)
    else:
        sd = sprint_id.strip()
        if not SPRINT_ID.match(sd):
            raise HarnessError("the sprint id is %r. Use sprint-NNN, three digits." % sprint_id)
        if any(sp.id == sd for sp in tree.sprints):
            raise HarnessError("%s already exists at %s. Pick another id." % (sd, rel(root, os.path.join(work_dir(root), "sprints", sd))))
    sdir = os.path.join(work_dir(root), "sprints", sd)
    fields = {"id": sd, "title": title, "starts": starts, "ends": ends}
    _, body = fm.parse(template_text(root, "sprint"))
    body = body.replace("{{ID}}", sd).replace("{{TITLE}}", title).replace("{{GOAL}}", goal or "(the user writes the goal)")
    sheet = os.path.join(sdir, sd + ".md")
    write_text(sheet, fm.dump(fields, body))
    os.makedirs(os.path.join(sdir, "ceremonies"), exist_ok=True)
    write_text(os.path.join(sdir, "ceremonies", ".gitkeep"), "")
    return {"id": sd, "path": rel(root, sheet)}
