"""The sprint clock: days remain, overdue sprints, no stored number.

Mutation proof (docs/MUTATION.md): M04 (days off by one) turned 4 tests red, 2 of them here.
"""
import os
import unittest

from tests.helpers import make_repo, rm, seed_board

from harness import board, clock


class ClockTest(unittest.TestCase):
    def setUp(self):
        self.root = make_repo()
        seed_board(self.root, starts="2026-09-01", ends="2026-09-14")

    def tearDown(self):
        os.environ.pop("HARNESS_TODAY", None)
        rm(self.root)

    def test_days_remaining_follows_today(self):
        tree = board.scan(self.root)
        sp = tree.sprints[0]
        os.environ["HARNESS_TODAY"] = "2026-09-04"
        self.assertEqual(clock.days_remaining(sp), 10)
        self.assertEqual(clock.sprint_status(sp), "active")
        os.environ["HARNESS_TODAY"] = "2026-08-20"
        self.assertEqual(clock.sprint_status(sp), "future")
        os.environ["HARNESS_TODAY"] = "2026-09-20"
        self.assertEqual(clock.days_remaining(sp), -6)
        self.assertEqual(clock.sprint_status(sp), "ended")

    def test_overdue_needs_open_tasks(self):
        os.environ["HARNESS_TODAY"] = "2026-09-20"
        tree = board.scan(self.root)
        late = clock.overdue(tree)
        self.assertEqual(len(late), 1)
        self.assertEqual(len(late[0][1]), 3)
        _, warnings = board.check(tree)
        self.assertTrue(any("ended on 2026-09-14 with 3 open" in w for w in warnings), warnings)
        self.assertIn("OVERDUE", board.board_text(tree))
        self.assertIn("The date does not move", board.board_text(tree))

    def test_undated_sprint(self):
        tree = board.scan(self.root)
        sp = tree.sprints[0]
        sp.ends = ""
        self.assertIsNone(clock.days_remaining(sp))
        self.assertEqual(clock.sprint_status(sp), "undated")

    def test_clock_report_text(self):
        os.environ["HARNESS_TODAY"] = "2026-09-04"
        tree = board.scan(self.root)
        report = clock.clock_report(tree)
        self.assertEqual(report["today"], "2026-09-04")
        self.assertEqual(report["sprints"][0]["days_remaining"], 10)
        self.assertIn("10 d remain", clock.clock_text(report))
        self.assertIn("never stored", clock.clock_text(report))


if __name__ == "__main__":
    unittest.main()
