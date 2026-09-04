"""The ceremonies: plan, triage, review, retro.

Mutation proof (docs/MUTATION.md): M11 (retro ignores the dates) turned test_retro_reads_the_journal_inside_the_dates red.
"""
import os
import unittest

from tests.helpers import make_repo, rm, seed_board

from harness import board, ceremonies, journal


class CeremonyTest(unittest.TestCase):
    def setUp(self):
        os.environ["HARNESS_TODAY"] = "2026-09-05"
        os.environ["HARNESS_NOW"] = "2026-09-05T10:00:00+00:00"
        self.root = make_repo()
        self.ids = seed_board(self.root)

    def tearDown(self):
        os.environ.pop("HARNESS_TODAY", None)
        os.environ.pop("HARNESS_NOW", None)
        rm(self.root)

    def test_every_ceremony_asks_and_never_answers(self):
        for name in ("plan", "triage", "review", "retro"):
            r = ceremonies.run(self.root, name)
            self.assertIn("Questions for the user", r["text"], name)
            self.assertIn("This document holds no verdict", r["text"], name)

    def test_plan_counts_backlog_sizes(self):
        tree = board.scan(self.root)
        board.new_task(self.root, tree, "Big one", work="L", eye="RUN")
        tree = board.scan(self.root)
        board.new_task(self.root, tree, "Unscoped", work="XL", eye="NONE")
        r = ceremonies.run(self.root, "plan")
        self.assertIn("Candidates from the backlog (2)", r["text"])
        self.assertIn("about 12.0 h of agent work and 30 min of eye", r["text"])
        self.assertIn("XL tasks not counted: TASK-0005", r["text"])

    def test_review_reports_verdict_queue_and_overdue(self):
        tree = board.scan(self.root)
        board.move(self.root, tree, self.ids["t2"], "in-progress")
        os.environ["HARNESS_TODAY"] = "2026-09-20"
        r = ceremonies.run(self.root, "review")
        self.assertIn("Awaiting a human verdict (1)", r["text"])
        self.assertIn("OVERDUE: the sprint ended on 2026-09-14 with 3 open", r["text"])
        self.assertIn("The date does not move", r["text"])

    def test_retro_reads_the_journal_inside_the_dates(self):
        journal.append(self.root, {"kind": "session", "ts": "2026-09-03T10:00:00+00:00", "slug": "a",
                                   "qa_closed": [{"id": "TASK-0001", "verdict": "ok"}], "qa_open": ["TASK-0002"],
                                   "surprises": ["the cache lied"], "failed": [], "commits": 2})
        journal.append(self.root, {"kind": "session", "ts": "2026-09-04T10:00:00+00:00", "slug": "b",
                                   "qa_closed": [], "qa_open": [], "surprises": [], "failed": ["the build"], "commits": 1})
        journal.append(self.root, {"kind": "session", "ts": "2026-08-01T10:00:00+00:00", "slug": "old",
                                   "qa_closed": [{"id": "X", "verdict": "ok"}], "qa_open": [], "surprises": ["old"], "failed": []})
        journal.append(self.root, {"kind": "observation", "ts": "2026-09-04T11:00:00+00:00", "stock": "wip", "current": 4, "target": 3})
        r = ceremonies.run(self.root, "retro")
        self.assertIn("sessions: 2", r["text"])
        self.assertIn("verdicts closed: 1 · items left open at a close: 1", r["text"])
        self.assertIn("the cache lied", r["text"])
        self.assertNotIn("- old", r["text"])
        self.assertIn("- the build", r["text"])
        self.assertIn("wip: 1 observation(s)", r["text"])

    def test_triage_flags(self):
        tree = board.scan(self.root)
        board.new_task(self.root, tree, "User thing", owner="user")
        r = ceremonies.run(self.root, "triage")
        self.assertIn("owner user with no due date", r["text"])
        self.assertIn("age not measured", r["text"])

    def test_write_puts_document_under_the_sprint(self):
        r = ceremonies.run(self.root, "review", write=True)
        self.assertEqual(r["path"], "work/sprints/sprint-001/ceremonies/2026-09-05-review.md")
        self.assertTrue(os.path.exists(os.path.join(self.root, r["path"])))


if __name__ == "__main__":
    unittest.main()
