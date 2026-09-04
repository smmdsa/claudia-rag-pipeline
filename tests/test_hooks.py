"""The hooks, fed with the documented payloads, with no Claude Code.

Mutation proof (docs/MUTATION.md): M06 (state folder not recognised) turned test_pre_write_denies_new_file_in_state_folder red.
"""
import io
import json
import os
import unittest
from contextlib import redirect_stderr, redirect_stdout

from tests.helpers import cli, make_repo, rm, seed_board

from harness import board, hooks, journal, state


def run_hook(root, name, payload):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = hooks.run(root, name, stream=io.StringIO(json.dumps(payload)))
    return code, out.getvalue(), err.getvalue()


def decision(out):
    try:
        return json.loads(out)["hookSpecificOutput"]["permissionDecision"]
    except (ValueError, KeyError):
        return None


class HookTest(unittest.TestCase):
    def setUp(self):
        os.environ["HARNESS_TODAY"] = "2026-09-05"
        self.root = make_repo()
        self.ids = seed_board(self.root)
        tree = board.scan(self.root)
        self.task = board.find(tree, "TASK-0001").path

    def tearDown(self):
        os.environ.pop("HARNESS_TODAY", None)
        rm(self.root)

    def test_pre_write_denies_new_file_in_state_folder(self):
        new = os.path.join(os.path.dirname(self.task), "TASK-0099-by-hand.md")
        code, out, _ = run_hook(self.root, "pre-write", {"tool_name": "Write", "tool_input": {"file_path": new}})
        self.assertEqual(code, 0)
        self.assertEqual(decision(out), "deny")
        self.assertIn("new task", out)

    def test_pre_write_allows_edit_of_existing_task(self):
        code, out, _ = run_hook(self.root, "pre-write", {"tool_name": "Edit", "tool_input": {"file_path": self.task}})
        self.assertEqual(code, 0)
        self.assertEqual(out, "")

    def test_pre_write_denies_tool_and_user_owned_files(self):
        for rel, needle in ((".harness/manifest.json", "harness tool"), (".harness/targets.json", "user-owned")):
            code, out, _ = run_hook(self.root, "pre-write", {"tool_name": "Edit", "tool_input": {"file_path": rel}})
            self.assertEqual(decision(out), "deny", rel)
            self.assertIn(needle, out)

    def test_pre_write_ignores_paths_outside_root(self):
        code, out, _ = run_hook(self.root, "pre-write", {"tool_name": "Write", "tool_input": {"file_path": "/tmp/elsewhere.md"}})
        self.assertEqual(out, "")

    def test_pre_bash_denies_hand_moves(self):
        for cmd in ("mv work/sprints/a/b/todo/x.md work/sprints/a/b/done/", "git mv work/backlog/x.md work/sprints/",
                    "cd x && rm -f work/backlog/TASK-0001.md", "rm work/sprints/sprint-001/epic-01/todo/x.md"):
            _, out, _ = run_hook(self.root, "pre-bash", {"tool_name": "Bash", "tool_input": {"command": cmd}})
            self.assertEqual(decision(out), "deny", cmd)
        for cmd in ("python3 -m harness start TASK-0001", "ls work/sprints", "grep -r x work/", "mv src/a.py src/b.py"):
            _, out, _ = run_hook(self.root, "pre-bash", {"tool_name": "Bash", "tool_input": {"command": cmd}})
            self.assertEqual(out, "", cmd)

    def test_post_work_runs_check_and_feeds_back_red(self):
        code, out, err = run_hook(self.root, "post-work", {"tool_name": "Edit", "tool_input": {"file_path": self.task}})
        self.assertEqual(code, 0)
        self.assertIn("GREEN", out)
        with open(self.task, "a", encoding="utf-8") as fh:
            fh.write("")
        dup = os.path.join(os.path.dirname(self.task), "TASK-0001-dup.md")
        with open(dup, "w", encoding="utf-8") as fh:
            fh.write("---\nid: TASK-0001\ntitle: d\nwork: S\neye: NONE\n---\n")
        code, out, err = run_hook(self.root, "post-work", {"tool_name": "Bash", "tool_input": {"command": "python3 -m harness new task --title x"}})
        self.assertEqual(code, 2)
        self.assertIn("used twice", err)

    def test_post_work_ignores_unrelated_tools(self):
        code, out, _ = run_hook(self.root, "post-work", {"tool_name": "Edit", "tool_input": {"file_path": "src/app.py"}})
        self.assertEqual((code, out), (0, ""))

    def test_stop_reports_verdict_queue_and_overdue(self):
        code, out, _ = run_hook(self.root, "stop", {"stop_hook_active": False})
        self.assertEqual((code, out), (0, ""))
        tree = board.scan(self.root)
        board.move(self.root, tree, "TASK-0002", "in-progress")
        os.environ["HARNESS_TODAY"] = "2026-09-20"
        code, out, _ = run_hook(self.root, "stop", {"stop_hook_active": False})
        msg = json.loads(out)["systemMessage"]
        self.assertIn("TASK-0002", msg)
        self.assertIn("sprint-001 ended on 2026-09-14", msg)
        code, out, _ = run_hook(self.root, "stop", {"stop_hook_active": True})
        self.assertEqual(out, "")

    def test_session_end_appends_observations(self):
        state.set_target(self.root, "wip", "0", by="user", why="none")
        tree = board.scan(self.root)
        board.move(self.root, tree, "TASK-0001", "in-progress")
        code, out, _ = run_hook(self.root, "session-end", {"reason": "other"})
        self.assertEqual(code, 0)
        self.assertIn("1 observation(s)", out)
        self.assertEqual(journal.observations(self.root)[0]["stock"], "wip")

    def test_session_start_initialises_and_prints_doctor(self):
        root = make_repo(init=False)
        try:
            code, out, _ = run_hook(root, "session-start", {"session_start_reason": "startup"})
            self.assertEqual(code, 0)
            self.assertIn("was not initialised", out)
            self.assertIn("HARNESS: sound", out)
        finally:
            rm(root)

    def test_empty_or_bad_payload_never_breaks(self):
        code, out, _ = run_hook(self.root, "pre-write", {})
        self.assertEqual(code, 0)
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = hooks.run(self.root, "stop", stream=io.StringIO("not json"))
        self.assertEqual(code, 0)
        code, out, _ = run_hook(self.root, "unknown-hook", {})
        self.assertEqual(code, 0)

    def test_cli_hook_entry_point(self):
        payload = json.dumps({"tool_name": "Edit", "tool_input": {"file_path": ".harness/targets.json"}})
        code, out, err = cli(self.root, "hook", "pre-write", stdin=payload)
        self.assertEqual(code, 0, err)
        self.assertEqual(decision(out), "deny")


if __name__ == "__main__":
    unittest.main()
