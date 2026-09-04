"""The command table. `python3 -m harness <command> [options]`.

Every read command accepts `--json`. Every command exits 0 on success and 1 on a
`HarnessError`. `check`, `doctor`, `rag health`, and `ports` use their exit code as
the verdict.
"""
import argparse
import json
import os
import sys

from harness import VERSION, board, ceremonies, dashboard, env, hooks, journal, manifest, ports, profile, rag, scaffold, session, state
from harness.board import scan
from harness.clock import clock_report, clock_text
from harness.util import HarnessError, emit, find_root


def _tree(root):
    if not os.path.isdir(os.path.join(root, "work")):
        raise HarnessError("no work/ directory under %s. Run `python3 -m harness init`." % root)
    return scan(root)


def build_parser():
    p = argparse.ArgumentParser(prog="python3 -m harness", description="An agent pipeline and a folder board for any repository.")
    p.add_argument("--root", help="repository root (default: HARNESS_ROOT, the git top level, or the current directory)")
    p.add_argument("--version", action="version", version="harness %s" % VERSION)
    sub = p.add_subparsers(dest="cmd", metavar="command")

    def add(name, help_, json_=True):
        sp = sub.add_parser(name, help=help_)
        if json_:
            sp.add_argument("--json", action="store_true", help="print JSON")
        return sp

    add("init", "create every missing harness file. Idempotent.").add_argument("--rebuild-manifest", action="store_true")
    add("doctor", "report the integrity of the install: exit 0 sound, 1 damaged, 2 not initialised")
    add("upgrade", "rewrite unchanged owned files from the new templates and record the version")
    add("uninstall", "remove the owned files that still match their checksum").add_argument("--yes", action="store_true", help="remove. Without it, print the plan.")
    add("adopt", "record a local edit of an owned file into the manifest").add_argument("file")
    add("restore", "write the template back over an owned file").add_argument("file")
    sp = add("hooks", "manage the hooks in .claude/settings.json")
    sp.add_argument("action", choices=["install"])

    sp = add("profile", "the project profile: architecture, languages, purpose, end user")
    sp.add_argument("action", choices=["show", "set", "ask"], nargs="?", default="show")
    sp.add_argument("pairs", nargs="*", help="key=value for `set`")
    sp = add("skills", "generate the project skills from the profile")
    sp.add_argument("action", choices=["generate"])

    add("board", "the whole picture, computed from the tree")
    add("next", "the first task the agent can start now. Tasks only the user can do print first.")
    sp = add("list", "one line per task")
    sp.add_argument("--sprint")
    sp.add_argument("--epic")
    sp.add_argument("--state", choices=board.STATES)
    sp.add_argument("--owner", choices=board.OWNER)
    add("show", "print one task file").add_argument("id")
    add("start", "todo -> in-progress", json_=False).add_argument("id")
    sp = add("done", "in-progress -> done. An eye task needs --verdict.", json_=False)
    sp.add_argument("id")
    sp.add_argument("--verdict", help="the user's words, verbatim")
    sp.add_argument("--by", default="user", help="who gave the verdict (default: user)")
    add("back", "in-progress -> todo", json_=False).add_argument("id")
    sp = add("priority", "set priority 1 on a task from the user's words, with the author and the date. --clear removes it.")
    sp.add_argument("id")
    sp.add_argument("--by", help="who named the task first. Never `agent`.")
    sp.add_argument("--why", help="the user's words, verbatim")
    sp.add_argument("--clear", action="store_true")
    sp = add("assign", "move a backlog task into the todo folder of an epic", json_=False)
    sp.add_argument("id")
    sp.add_argument("--epic", required=True)
    add("check", "measure the shape of the tree. Exit 1 on any error.")
    add("clock", "the days that remain in each sprint, computed from today")

    sp = add("new", "create a task, an epic, or a sprint from the templates")
    sp.add_argument("kind", choices=["task", "epic", "sprint"])
    sp.add_argument("--title", required=True)
    sp.add_argument("--epic", help="task: the epic id. Without it the task goes to the backlog.")
    sp.add_argument("--sprint", help="epic: the sprint id")
    sp.add_argument("--work", default=None)
    sp.add_argument("--eye", default=None)
    sp.add_argument("--owner", default="agent")
    sp.add_argument("--due", default="")
    sp.add_argument("--blocked-by", action="append", default=[])
    sp.add_argument("--needs-decision", default="")
    sp.add_argument("--ref", action="append", default=[])
    sp.add_argument("--starts", help="sprint: YYYY-MM-DD")
    sp.add_argument("--ends", help="sprint: YYYY-MM-DD")
    sp.add_argument("--goal", default="")

    sp = add("ceremony", "plan, triage, review, or retro: a document with an agenda and open questions")
    sp.add_argument("name", choices=list(ceremonies.CEREMONIES))
    sp.add_argument("--sprint")
    sp.add_argument("--write", action="store_true", help="write the document under the sprint's ceremonies/")

    add("state", "every stock, computed now, against the declared targets")
    sp = add("target", "show or set a target. The user declares targets.")
    sp.add_argument("action", choices=["show", "set"])
    sp.add_argument("stock", nargs="?")
    sp.add_argument("value", nargs="?")
    sp.add_argument("--by")
    sp.add_argument("--why")
    sp = add("escalate", "append an observation the agent cannot decide to .harness/escalations.md", json_=False)
    sp.add_argument("--title", required=True)
    sp.add_argument("--observed", required=True)
    sp.add_argument("--level", required=True)
    sp.add_argument("--decision-needed", required=True)
    sp = add("journal", "read or append the journal")
    sp.add_argument("action", choices=["tail", "observe"])
    sp.add_argument("-n", type=int, default=5)

    sp = add("session", "open, draft, or close a session")
    sp.add_argument("action", choices=["open", "draft", "close"])
    sp.add_argument("--slug")
    sp.add_argument("--no-rag", action="store_true", help="open: skip the RAG canary")
    sp.add_argument("--qa-closed", action="append", default=[], help="close: TASK-NNNN=verdict[:how]")
    sp.add_argument("--qa-open", action="append", default=[])
    sp.add_argument("--surprise", action="append", default=[])
    sp.add_argument("--failed", action="append", default=[])
    sp.add_argument("--no-reindex", action="store_true")

    add("ports", "check every port the harness binds. Exit 1 when one is taken.")
    add("env", "derive and write .harness/env.local")
    sp = add("rag", "the search index: health, config, update")
    sp.add_argument("action", choices=["health", "config", "update"])
    sp.add_argument("--state-url")
    sp = add("dashboard", "the board dashboard: build-db, serve, static")
    sp.add_argument("action", choices=["build-db", "serve", "static"])
    sp.add_argument("--port", type=int)
    sp.add_argument("--host", default="127.0.0.1")
    sp.add_argument("--rebuild-every", type=int, default=0, help="serve: seconds between cache rebuilds")
    sp.add_argument("--db")
    sp.add_argument("-o", "--out", default="board.html")
    sp = add("hook", "hook entry point. Reads the payload on stdin.", json_=False)
    sp.add_argument("name")
    return p


def run(args):
    root = os.path.realpath(args.root) if args.root else find_root()
    js = getattr(args, "json", False)
    c = args.cmd

    if c == "init":
        r = scaffold.init(root, rebuild_manifest=args.rebuild_manifest)
        emit(r, js, scaffold.init_text)
        return 0
    if c == "doctor":
        r = manifest.doctor(root)
        emit(r, js, manifest.doctor_text)
        return r["exit"]
    if c == "upgrade":
        r = scaffold.upgrade(root)
        emit(r, js, lambda r: "upgrade %s -> %s: %d rewritten, %d edited and kept, %d created%s" % (
            r["from"], r["to"], len(r["rewritten"]), len(r["edited_kept"]), len(r["created"]),
            ("\n  edited and kept: " + ", ".join(r["edited_kept"])) if r["edited_kept"] else ""))
        return 0
    if c == "uninstall":
        r = scaffold.uninstall(root, dry_run=not args.yes)
        emit(r, js, lambda r: "%s%d file(s) removed, %d kept\n%s\n  %s" % (
            "DRY RUN: " if r["dry_run"] else "", len(r["removed"]), len(r["kept"]),
            "\n".join("  - " + f for f in r["removed"]) + ("\n" if r["removed"] else "") +
            "\n".join("  keep %s (%s)" % k for k in r["kept"]), r["note"]))
        return 0
    if c == "adopt":
        emit(scaffold.adopt(root, args.file), js, lambda r: "adopted %s" % r["adopted"])
        return 0
    if c == "restore":
        r = scaffold.restore(root, args.file)
        emit(r, js, lambda r: (r["diff"] or "(no difference)\n") + "restored %s" % r["restored"])
        return 0
    if c == "hooks":
        r = scaffold.install_hooks(root)
        emit(r, js, lambda r: "hooks installed: %s" % (", ".join(r["added"]) or "all present already"))
        return 0

    if c == "profile":
        if args.action == "show":
            emit(profile.show(root), js, profile.profile_text)
        elif args.action == "set":
            pairs = []
            for pair in args.pairs:
                if "=" not in pair:
                    raise HarnessError("use key=value, not %r" % pair)
                pairs.append(tuple(pair.split("=", 1)))
            emit(profile.set_values(root, pairs), js, profile.profile_text)
        else:
            emit(profile.ask(root), js, profile.profile_text)
        return 0
    if c == "skills":
        r = profile.generate_skills(root)
        emit({"written": r}, js, lambda r: "written: " + ", ".join(r["written"]))
        return 0

    if c == "board":
        tree = _tree(root)
        emit(board.tree_dict(tree), js, lambda d: board.board_text(tree))
        return 0
    if c == "next":
        tree = _tree(root)
        users, agents = board.next_tasks(tree)
        emit({"user": [board.task_dict(t, root) for t in users], "next": board.task_dict(agents[0], root) if agents else None,
              "decisions": board.waiting_decisions(tree)}, js, lambda d: board.next_text(tree, root))
        return 0
    if c == "list":
        tree = _tree(root)
        tasks = board.filter_tasks(tree, args.sprint, args.epic, args.state, args.owner)
        emit([board.task_dict(t, root) for t in tasks], js,
             lambda d: "\n".join(board._line(t, tree) for t in tasks) or "  no task matches the filter")
        return 0
    if c == "show":
        tree = _tree(root)
        t = board.find(tree, args.id)
        if t is None:
            raise HarnessError("no task with id %s." % args.id)
        emit(dict(board.task_dict(t, root), body=t.body), js, lambda d: open(t.path, encoding="utf-8").read())
        return 0
    if c in ("start", "done", "back"):
        tree = _tree(root)
        to = {"start": "in-progress", "done": "done", "back": "todo"}[c]
        r = board.move(root, tree, args.id, to, verdict=getattr(args, "verdict", None), by=getattr(args, "by", None))
        print("%s: %s -> %s (%s)" % (r["id"], r["from"], r["to"], r["how"]))
        if r["note"]:
            print("  note: " + r["note"])
        return 0
    if c == "assign":
        tree = _tree(root)
        r = board.assign(root, tree, args.id, args.epic)
        print("%s -> %s todo (%s)" % (r["id"], r["epic"], r["how"]))
        return 0
    if c == "priority":
        tree = _tree(root)
        r = board.set_priority(root, tree, args.id, by=args.by, why=args.why, clear=args.clear)
        emit(r, js, lambda r: "%s: priority cleared" % r["id"] if not r["priority"]
             else "%s: priority 1 by %s on %s" % (r["id"], r["by"], r["date"]))
        return 0
    if c == "check":
        tree = _tree(root)
        errors, warnings = board.check(tree, wip_cap=state.wip_cap(root))
        emit({"errors": errors, "warnings": warnings, "tasks": len(board.all_tasks(tree)), "ok": not errors}, js,
             lambda d: board.check_text(errors, warnings, len(board.all_tasks(tree))))
        return 1 if errors else 0
    if c == "clock":
        tree = _tree(root)
        emit(clock_report(tree), js, clock_text)
        return 0
    if c == "new":
        tree = _tree(root)
        if args.kind == "task":
            r = board.new_task(root, tree, args.title, epic=args.epic, work=args.work or "S", eye=args.eye or "NONE",
                               owner=args.owner, due=args.due, blocked_by=args.blocked_by,
                               decision=args.needs_decision, refs=args.ref)
            emit(r, js, lambda r: "%s created at %s. Write Why, What to do, Done when, Not covered." % (r["id"], r["path"]))
        elif args.kind == "epic":
            if not args.sprint:
                raise HarnessError("an epic needs --sprint <id>.")
            r = board.new_epic(root, tree, args.sprint, args.title, work=args.work or "M", eye=args.eye or "GLANCE")
            emit(r, js, lambda r: "%s created at %s" % (r["id"], r["path"]))
        else:
            if not (args.starts and args.ends):
                raise HarnessError("a sprint needs --starts and --ends (YYYY-MM-DD).")
            r = board.new_sprint(root, tree, args.title, args.starts, args.ends, goal=args.goal)
            emit(r, js, lambda r: "%s created at %s" % (r["id"], r["path"]))
        return 0

    if c == "ceremony":
        r = ceremonies.run(root, args.name, sprint_id=args.sprint, write=args.write)
        emit(r, js, lambda r: r["text"] + ("\nwritten to %s" % r["path"] if r["path"] else ""))
        return 0
    if c == "state":
        rows = state.measure(root)
        emit(rows, js, state.state_text)
        return 0
    if c == "target":
        if args.action == "show":
            emit(state.read_targets(root), js, lambda d: json.dumps(d, indent=2, ensure_ascii=False))
        else:
            if not (args.stock and args.value):
                raise HarnessError("use: target set <stock> <value> --by <who> --why \"<text>\"")
            r = state.set_target(root, args.stock, args.value, args.by, args.why)
            emit(r, js, lambda r: "target %s = %s (by %s on %s)" % (args.stock, r["value"], r["decided_by"], r["date"]))
        return 0
    if c == "escalate":
        p = state.escalate(root, args.title, args.observed, args.level, args.decision_needed)
        print("appended to %s. The decision stays empty until the user writes it." % os.path.relpath(p, root))
        return 0
    if c == "journal":
        if args.action == "tail":
            lines, bad = journal.read(root)
            emit({"lines": lines[-args.n:], "malformed": bad}, js,
                 lambda d: "\n".join(json.dumps(l, ensure_ascii=False) for l in d["lines"]) + ("\n%d malformed line(s)" % len(bad) if bad else ""))
        else:
            r = state.observe(root)
            emit({"written": r}, js, lambda d: "%d observation(s) appended" % len(r))
        return 0

    if c == "session":
        if args.action == "open":
            b = session.open_brief(root, with_rag=not args.no_rag)
            emit(b, js, session.open_text)
        elif args.action == "draft":
            p = session.draft(root, args.slug)
            emit({"path": p}, js, lambda d: "draft written at %s. Fill TL;DR, What happened, Open items, How to resume." % p)
        else:
            if not args.slug:
                raise HarnessError("close needs --slug <YYYY-MM-DD-HHMM>.")
            r = session.close(root, args.slug, qa_closed=args.qa_closed, qa_open=args.qa_open,
                              surprises=args.surprise, failed=args.failed, reindex=not args.no_reindex)
            emit(r, js, session.close_text)
        return 0

    if c == "ports":
        rows = ports.check_ports()
        emit(rows, js, ports.ports_text)
        return 0 if ports.all_free(rows) else 1
    if c == "env":
        emit(env.write(root), js, env.env_text)
        return 0
    if c == "rag":
        if args.action == "health":
            r = rag.health(root, url=args.state_url)
            emit(r, js, rag.health_text)
            return r["exit"]
        if args.action == "config":
            emit(rag.write_config(root), js, lambda r: "written %s with collections %s" % (r["path"], ", ".join(r["collections"])))
            return 0
        r = rag.request_update(root, url=args.state_url)
        emit(r, js, lambda r: "re-index %s" % ("requested: %s" % r["note"] if r["ok"] else "FAILED: %s" % r["note"]))
        return 0 if r["ok"] else 1
    if c == "dashboard":
        if args.action == "build-db":
            emit(dashboard.build_db(root, args.db), js, lambda r: "cache %s: %d task(s), %d sprint(s). The tree stays the truth." % (r["db"], r["tasks"], r["sprints"]))
        elif args.action == "static":
            emit(dashboard.static(root, args.out, db=args.db), js, lambda r: "written %s (%d bytes, cache built %s)" % (r["out"], r["bytes"], r["built_at"]))
        else:
            dashboard.serve(root, port=args.port, host=args.host, rebuild_every=args.rebuild_every, db=args.db)
        return 0
    if c == "hook":
        return hooks.run(root, args.name)
    return 0


def main(argv):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.cmd:
        parser.print_help()
        return 0
    try:
        return run(args)
    except HarnessError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
