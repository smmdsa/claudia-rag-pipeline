"""The board: scan, next, moves, verdicts, check, new.

Mutation proof (docs/MUTATION.md): M01 (no verdict needed) 2 red, M02 (blockers ignored) 1 red, M15 (any work size) 1 red,
M16 (priority without provenance accepted) 1 red,
M40 (a section ends at the end of the file) 4 red.
"""
import os
import unittest

from tests.helpers import cli, commit_all, make_repo, rm, seed_board

from harness import board
from harness.util import HarnessError, read_text, write_text


class BoardTest(unittest.TestCase):
    def setUp(self):
        os.environ["HARNESS_TODAY"] = "2026-09-05"
        self.root = make_repo()
        self.ids = seed_board(self.root)

    def tearDown(self):
        os.environ.pop("HARNESS_TODAY", None)
        rm(self.root)

    def test_ids_are_global_and_sequential(self):
        self.assertEqual((self.ids["t1"], self.ids["t2"], self.ids["t3"]), ("TASK-0001", "TASK-0002", "TASK-0003"))
        tree = board.scan(self.root)
        backlog = board.new_task(self.root, tree, "Backlog one")
        self.assertEqual(backlog["id"], "TASK-0004")
        self.assertIsNone(backlog["epic"])
        self.assertTrue(backlog["path"].startswith("work/backlog/"))

    def test_scan_reads_state_from_the_folder(self):
        tree = board.scan(self.root)
        self.assertEqual(len(tree.sprints), 1)
        self.assertEqual([t.state for t in board.all_tasks(tree)], ["todo", "todo", "todo"])
        self.assertEqual(board.find(tree, "task-0002").eye, "RUN")

    def test_next_skips_blocked_and_ranks_due_then_priority(self):
        tree = board.scan(self.root)
        users, agents = board.next_tasks(tree)
        self.assertEqual([t.id for t in agents], ["TASK-0001", "TASK-0002"])  # 0003 waits for 0001
        board.new_task(self.root, tree, "Urgent", epic=self.ids["epic"], due="2026-09-10")
        tree = board.scan(self.root)
        board.new_task(self.root, tree, "Named first", epic=self.ids["epic"])
        tree = board.scan(self.root)
        board.set_priority(self.root, tree, "TASK-0005", by="user", why="this one opens the sprint")
        tree = board.scan(self.root)
        _, agents = board.next_tasks(tree)
        self.assertEqual([t.id for t in agents][:2], ["TASK-0004", "TASK-0005"])

    def test_priority_with_provenance_is_valid(self):
        tree = board.scan(self.root)
        r = board.set_priority(self.root, tree, "TASK-0002", by="user", why="the login is what the client asked for")
        self.assertEqual((r["priority"], r["by"], r["date"]), (1, "user", "2026-09-05"))
        text = read_text(os.path.join(self.root, r["path"]))
        self.assertIn("priority: 1\npriority-by: user\npriority-date: 2026-09-05\npriority-why:", text)
        tree = board.scan(self.root)
        t = board.find(tree, "TASK-0002")
        self.assertEqual((t.priority, t.priority_by, t.priority_why), (1, "user", "the login is what the client asked for"))
        errors, _ = board.check(tree)
        self.assertEqual(errors, [])
        self.assertIn("priority 1 by user", board.board_text(tree))
        _, agents = board.next_tasks(tree)
        self.assertEqual(agents[0].id, "TASK-0002")
        board.set_priority(self.root, tree, "TASK-0002", clear=True)
        tree = board.scan(self.root)
        self.assertEqual(board.find(tree, "TASK-0002").priority, 0)
        self.assertNotIn("priority", read_text(board.find(tree, "TASK-0002").path))

    def test_priority_without_provenance_turns_check_red(self):
        tree = board.scan(self.root)
        t = board.find(tree, "TASK-0001")
        text = read_text(t.path)  # read first: `open(path, "w")` truncates before a read in the same expression
        self.assertIn("owner: agent\n", text)
        with open(t.path, "w", encoding="utf-8") as fh:
            fh.write(text.replace("owner: agent\n", "owner: agent\npriority: 1\n"))
        errors, _ = board.check(board.scan(self.root))
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("TASK-0001 carries priority 1 with no author or no date", errors[0])
        self.assertIn("python3 -m harness priority TASK-0001 --by user --why", errors[0])
        # the agent as author is an opinion too
        text = read_text(t.path)
        with open(t.path, "w", encoding="utf-8") as fh:
            fh.write(text.replace("priority: 1\n", "priority: 1\npriority-by: agent\npriority-date: 2026-09-05\n"))
        errors, _ = board.check(board.scan(self.root))
        self.assertEqual(len(errors), 1)
        self.assertIn("the agent set", errors[0])

    def test_priority_command_records_the_author(self):
        tree = board.scan(self.root)
        with self.assertRaises(HarnessError):
            board.set_priority(self.root, tree, "TASK-0001", by="user", why="")
        with self.assertRaises(HarnessError):
            board.set_priority(self.root, tree, "TASK-0001", by="agent", why="I think so")
        with self.assertRaises(HarnessError):
            board.set_priority(self.root, tree, "TASK-9999", by="user", why="x")
        code, out, err = cli(self.root, "priority", "TASK-0001", "--by", "user", "--why", "first thing tomorrow")
        self.assertEqual(code, 0, err)
        self.assertIn("TASK-0001: priority 1 by user on", out)
        code, out, err = cli(self.root, "priority", "TASK-0003", "--by", "agent", "--why", "x")
        self.assertEqual(code, 1)
        self.assertIn("agent cannot set", err)
        code, _, _ = cli(self.root, "check")
        self.assertEqual(code, 0)

    def test_next_reports_user_owned_first(self):
        tree = board.scan(self.root)
        board.new_task(self.root, tree, "Only the user", epic=self.ids["epic"], owner="user")
        tree = board.scan(self.root)
        users, agents = board.next_tasks(tree)
        self.assertEqual([t.id for t in users], ["TASK-0004"])
        self.assertNotIn("TASK-0004", [t.id for t in agents])
        self.assertIn("wait on the user", board.next_text(tree, self.root))

    def test_needs_decision_is_not_ready(self):
        tree = board.scan(self.root)
        board.new_task(self.root, tree, "Waits", epic=self.ids["epic"], decision="D1")
        tree = board.scan(self.root)
        t = board.find(tree, "TASK-0004")
        self.assertFalse(board.ready(t, tree))
        self.assertIn("D1", board.why_not_ready(t, tree))
        with self.assertRaises(HarnessError):
            board.move(self.root, tree, "TASK-0004", "in-progress")

    def test_move_uses_git_mv_when_tracked(self):
        commit_all(self.root)
        tree = board.scan(self.root)
        r = board.move(self.root, tree, "TASK-0001", "in-progress")
        self.assertEqual(r["how"], "git mv")
        self.assertIn("/in-progress/", r["path"])
        self.assertTrue(os.path.exists(os.path.join(self.root, r["path"])))
        tree = board.scan(self.root)
        self.assertEqual(board.find(tree, "TASK-0001").state, "in-progress")

    def test_move_falls_back_to_rename_when_untracked(self):
        tree = board.scan(self.root)
        r = board.move(self.root, tree, "TASK-0001", "in-progress")
        self.assertTrue(r["how"].startswith("rename"))

    def test_done_on_eye_task_needs_verdict(self):
        tree = board.scan(self.root)
        board.move(self.root, tree, "TASK-0002", "in-progress")
        tree = board.scan(self.root)
        with self.assertRaises(HarnessError) as cm:
            board.move(self.root, tree, "TASK-0002", "done")
        self.assertIn("verdict", str(cm.exception))
        tree = board.scan(self.root)
        self.assertEqual(board.find(tree, "TASK-0002").state, "in-progress")

    def test_done_with_verdict_writes_task_and_epic(self):
        tree = board.scan(self.root)
        board.move(self.root, tree, "TASK-0002", "in-progress")
        tree = board.scan(self.root)
        r = board.move(self.root, tree, "TASK-0002", "done", verdict="it runs on my screen", by="user")
        self.assertEqual(r["to"], "done")
        text = read_text(os.path.join(self.root, r["path"]))
        self.assertIn("## Verdict", text)
        self.assertIn("it runs on my screen", text)
        self.assertIn("2026-09-05", text)
        tree = board.scan(self.root)
        _, ep = board.find_epic(tree, self.ids["epic"])
        self.assertIn("TASK-0002 · \"it runs on my screen\"", read_text(ep.sheet))
        self.assertTrue(board.find(tree, "TASK-0002").has_verdict())

    def _sheet(self, text):
        p = os.path.join(self.root, "sheet.md")
        write_text(p, text)
        return p

    def test_append_section_writes_inside_a_section_in_the_middle(self):
        p = self._sheet("# E\n\n## Verdicts\n\n(none)\n\n## Out of scope\n\nnothing\n")
        board._append_section(p, "## Verdicts", "- one")
        text = read_text(p)
        self.assertLess(text.index("- one"), text.index("## Out of scope"))

    def test_append_section_accumulates_in_order(self):
        p = self._sheet("# E\n\n## Verdicts\n\n(none)\n\n## Out of scope\n\nnothing\n")
        board._append_section(p, "## Verdicts", "- one")
        board._append_section(p, "## Verdicts", "- two")
        text = read_text(p)
        self.assertLess(text.index("- one"), text.index("- two"))
        self.assertLess(text.index("- two"), text.index("## Out of scope"))

    def test_append_section_writes_at_the_end_when_the_section_is_last(self):
        p = self._sheet("# E\n\n## Out of scope\n\nnothing\n\n## Verdicts\n\n(none)\n")
        board._append_section(p, "## Verdicts", "- one")
        text = read_text(p)
        self.assertLess(text.index("## Verdicts"), text.index("- one"))
        self.assertTrue(text.endswith("- one\n"))

    def test_append_section_creates_the_header_when_it_is_missing(self):
        p = self._sheet("# E\n\n## Out of scope\n\nnothing\n")
        board._append_section(p, "## Verdict", "- one")
        text = read_text(p)
        self.assertLess(text.index("## Verdict\n"), text.index("- one"))

    def test_append_section_keeps_a_deeper_header_inside_the_section(self):
        p = self._sheet("# E\n\n## Verdicts\n\n### 2026\n\n(none)\n\n## Out of scope\n\nnothing\n")
        board._append_section(p, "## Verdicts", "- one")
        text = read_text(p)
        self.assertLess(text.index("### 2026"), text.index("- one"))
        self.assertLess(text.index("- one"), text.index("## Out of scope"))

    def test_done_writes_the_epic_verdict_under_its_own_header(self):
        tree = board.scan(self.root)
        board.move(self.root, tree, "TASK-0002", "in-progress")
        tree = board.scan(self.root)
        board.move(self.root, tree, "TASK-0002", "done", verdict="it runs on my screen", by="user")
        tree = board.scan(self.root)
        _, ep = board.find_epic(tree, self.ids["epic"])
        text = read_text(ep.sheet)
        self.assertLess(text.index("## Verdicts"), text.index("it runs on my screen"))
        self.assertLess(text.index("it runs on my screen"), text.index("## Out of scope"))

    def test_done_on_eye_none_needs_no_verdict(self):
        tree = board.scan(self.root)
        board.move(self.root, tree, "TASK-0001", "in-progress")
        tree = board.scan(self.root)
        r = board.move(self.root, tree, "TASK-0001", "done")
        self.assertEqual(r["to"], "done")
        tree = board.scan(self.root)
        self.assertTrue(board.ready(board.find(tree, "TASK-0003"), tree))

    def test_back_and_illegal_transitions(self):
        tree = board.scan(self.root)
        with self.assertRaises(HarnessError):
            board.move(self.root, tree, "TASK-0001", "done")  # todo -> done is not a transition
        board.move(self.root, tree, "TASK-0001", "in-progress")
        tree = board.scan(self.root)
        board.move(self.root, tree, "TASK-0001", "todo")
        tree = board.scan(self.root)
        self.assertEqual(board.find(tree, "TASK-0001").state, "todo")
        with self.assertRaises(HarnessError):
            board.move(self.root, tree, "TASK-0001", "todo")

    def test_assign_backlog_task(self):
        tree = board.scan(self.root)
        board.new_task(self.root, tree, "From backlog")
        tree = board.scan(self.root)
        with self.assertRaises(HarnessError):
            board.move(self.root, tree, "TASK-0004", "in-progress")
        r = board.assign(self.root, tree, "TASK-0004", self.ids["epic"])
        self.assertIn("/todo/", r["path"])
        tree = board.scan(self.root)
        self.assertEqual(board.find(tree, "TASK-0004").epic, self.ids["epic"])

    def test_check_green_on_seed(self):
        errors, warnings = board.check(board.scan(self.root))
        self.assertEqual(errors, [])

    def test_check_finds_shape_errors(self):
        tree = board.scan(self.root)
        t = board.find(tree, "TASK-0003")
        text = read_text(t.path).replace("work: S", "work: HUGE").replace("blocked-by:\n  - TASK-0001", "blocked-by:\n  - TASK-9999")
        with open(t.path, "w", encoding="utf-8") as fh:
            fh.write(text)
        dup = os.path.join(os.path.dirname(t.path), "TASK-0001-dup.md")
        with open(dup, "w", encoding="utf-8") as fh:
            fh.write("---\nid: TASK-0001\ntitle: dup\nwork: S\neye: NONE\n---\n")
        errors, _ = board.check(board.scan(self.root))
        joined = "\n".join(errors)
        self.assertIn("work is 'HUGE'", joined)
        self.assertIn("TASK-9999", joined)
        self.assertIn("used twice", joined)

    def test_check_flags_done_eye_task_without_verdict(self):
        tree = board.scan(self.root)
        t = board.find(tree, "TASK-0002")
        dst = os.path.join(os.path.dirname(os.path.dirname(t.path)), "done", os.path.basename(t.path))
        os.rename(t.path, dst)
        errors, _ = board.check(board.scan(self.root))
        self.assertTrue(any("no `## Verdict`" in e for e in errors), errors)

    def test_check_flags_done_with_open_blocker(self):
        tree = board.scan(self.root)
        t = board.find(tree, "TASK-0003")
        dst = os.path.join(os.path.dirname(os.path.dirname(t.path)), "done", os.path.basename(t.path))
        os.rename(t.path, dst)
        errors, _ = board.check(board.scan(self.root))
        self.assertTrue(any("blocker TASK-0001 is not" in e for e in errors), errors)

    def test_check_wip_cap_warning(self):
        for i in range(4):
            tree = board.scan(self.root)
            r = board.new_task(self.root, tree, "W%d" % i, epic=self.ids["epic"])
            tree = board.scan(self.root)
            board.move(self.root, tree, r["id"], "in-progress")
        _, warnings = board.check(board.scan(self.root))
        self.assertTrue(any("cap is 3" in w for w in warnings), warnings)
        _, warnings = board.check(board.scan(self.root), wip_cap=10)
        self.assertFalse(any("cap is" in w for w in warnings), warnings)

    def test_new_task_rejects_bad_sizes(self):
        tree = board.scan(self.root)
        with self.assertRaises(HarnessError):
            board.new_task(self.root, tree, "bad", work="XXL")
        with self.assertRaises(HarnessError):
            board.new_task(self.root, tree, "bad", eye="LOOK")
        with self.assertRaises(HarnessError):
            board.new_task(self.root, tree, "bad", due="next week")

    def test_new_sprint_rejects_ends_before_starts(self):
        tree = board.scan(self.root)
        with self.assertRaises(HarnessError):
            board.new_sprint(self.root, tree, "x", "2026-09-10", "2026-09-01")

    def test_board_text_is_computed_and_names_next(self):
        text = board.board_text(board.scan(self.root))
        self.assertIn("computed from the folder tree", text)
        self.assertIn("NEXT: TASK-0001", text)
        self.assertIn("9 d remain", text)

    def test_cli_round_trip(self):
        code, out, _ = cli(self.root, "board")
        self.assertEqual(code, 0)
        self.assertIn("sprint-001", out)
        code, out, _ = cli(self.root, "next", "--json")
        self.assertEqual(code, 0)
        self.assertIn('"TASK-0001"', out)
        code, out, err = cli(self.root, "start", "TASK-0001")
        self.assertEqual(code, 0, err)
        code, out, err = cli(self.root, "done", "TASK-0001")
        self.assertEqual(code, 0, err)
        code, _, _ = cli(self.root, "check")
        self.assertEqual(code, 0)
        code, out, err = cli(self.root, "start", "TASK-0002")
        code, out, err = cli(self.root, "done", "TASK-0002")
        self.assertEqual(code, 1)
        self.assertIn("verdict", err)


if __name__ == "__main__":
    unittest.main()
