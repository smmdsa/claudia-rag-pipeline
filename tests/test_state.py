"""Targets, computed state, observations, escalations.

Mutation proof (docs/MUTATION.md): M05 (observe twice a day) turned test_observe_once_per_stock_per_day red.
"""
import json
import os
import unittest

from tests.helpers import cli, commit_all, make_repo, rm, seed_board

from harness import board, journal, state
from harness.util import HarnessError, read_text


class StateTest(unittest.TestCase):
    def setUp(self):
        os.environ["HARNESS_TODAY"] = "2026-09-05"
        self.root = make_repo()
        self.ids = seed_board(self.root)

    def tearDown(self):
        os.environ.pop("HARNESS_TODAY", None)
        rm(self.root)

    def rows(self):
        return {r["stock"]: r for r in state.measure(self.root)}

    def test_target_needs_author_and_reason(self):
        with self.assertRaises(HarnessError):
            state.set_target(self.root, "eye_queue", "5", by="", why="")
        with self.assertRaises(HarnessError):
            state.set_target(self.root, "nonsense", "5", by="user", why="x")
        with self.assertRaises(HarnessError):
            state.set_target(self.root, "eye_queue", "five", by="user", why="x")
        t = state.set_target(self.root, "eye_queue", "1", by="user", why="one person checks")
        self.assertEqual(t["decided_by"], "user")
        data = json.loads(read_text(os.path.join(self.root, ".harness", "targets.json")))
        self.assertEqual(data["targets"]["eye_queue"]["why"], "one person checks")

    def test_stocks_measure_the_tree(self):
        r = self.rows()
        self.assertEqual(r["wip"]["current"], 0)
        self.assertEqual(r["backlog_size"]["current"], 0)
        self.assertEqual(r["eye_queue"]["current"], 0)
        self.assertEqual(r["eye_queue_age_days"]["current"], 0)
        self.assertIsNone(r["days_since_session"]["current"])
        self.assertIn("no session", r["days_since_session"]["reason"])
        self.assertIsNone(r["front_stale_days"]["current"])

    def test_unmeasured_age_is_not_zero(self):
        tree = board.scan(self.root)
        board.move(self.root, tree, self.ids["t2"], "in-progress")
        r = self.rows()
        self.assertEqual(r["eye_queue"]["current"], 1)
        self.assertIsNone(r["eye_queue_age_days"]["current"])
        self.assertIn("not committed", r["eye_queue_age_days"]["reason"])
        self.assertIn("not measured", state.state_text(state.measure(self.root)))

    def test_age_measured_from_git(self):
        commit_all(self.root)
        tree = board.scan(self.root)
        board.move(self.root, tree, self.ids["t2"], "in-progress")
        commit_all(self.root, "start")
        r = self.rows()
        self.assertIsNotNone(r["eye_queue_age_days"]["current"])
        self.assertLess(r["eye_queue_age_days"]["current"], 1)

    def test_gap_and_over(self):
        state.set_target(self.root, "wip", "0", by="user", why="none")
        tree = board.scan(self.root)
        board.move(self.root, tree, self.ids["t1"], "in-progress")
        r = self.rows()
        self.assertEqual(r["wip"]["gap"], 1)
        self.assertTrue(r["wip"]["over"])
        self.assertEqual(state.wip_cap(self.root), 0)

    def test_observe_once_per_stock_per_day(self):
        state.set_target(self.root, "wip", "0", by="user", why="none")
        tree = board.scan(self.root)
        board.move(self.root, tree, self.ids["t1"], "in-progress")
        first = state.observe(self.root)
        second = state.observe(self.root)
        self.assertEqual(len(first), 1)
        self.assertEqual(second, [])
        obs = journal.observations(self.root)
        self.assertEqual(obs[0]["stock"], "wip")
        self.assertEqual(obs[0]["decided_by"], "user")

    def test_escalate_leaves_decision_empty(self):
        p = state.escalate(self.root, "The objective", "82 commits, 0 verdicts", "objective", "build or check?")
        text = read_text(p)
        self.assertIn("## 2026-09-05 · The objective", text)
        self.assertIn("**Decision:** (empty", text)

    def test_cli_state_and_target(self):
        code, out, err = cli(self.root, "target", "set", "backlog_size", "10", "--by", "user", "--why", "fits a screen")
        self.assertEqual(code, 0, err)
        code, out, _ = cli(self.root, "state")
        self.assertEqual(code, 0)
        self.assertIn("backlog_size", out)
        self.assertIn("computed now", out)
        code, out, err = cli(self.root, "target", "set", "backlog_size", "10")
        self.assertEqual(code, 1)
        self.assertIn("--by", err)


if __name__ == "__main__":
    unittest.main()
