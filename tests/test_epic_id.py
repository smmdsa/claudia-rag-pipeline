"""An epic id repeats across sprints, and a verdict must land in its own sprint.

Every sprint numbers its epics from EP-01. A lookup that returns the first match sends
the verdict of a task in one sprint to the epic sheet of another sprint. The reader
sees a green board and a verdict under the wrong goal.

Mutation proof (docs/MUTATION.md): M34, M35, M36.
"""
import os
import unittest

from tests.helpers import make_repo, rm

from harness import board
from harness.util import HarnessError, read_text


class EpicIdTest(unittest.TestCase):
    def setUp(self):
        self.root = make_repo()
        tree = board.scan(self.root)
        board.new_sprint(self.root, tree, "Zero", "2026-09-01", "2026-09-30", sprint_id="sprint-000")
        tree = board.scan(self.root)
        board.new_sprint(self.root, tree, "One", "2026-09-01", "2026-09-30")
        tree = board.scan(self.root)
        self.e0 = board.new_epic(self.root, tree, "sprint-000", "Zero epic")
        tree = board.scan(self.root)
        self.e1 = board.new_epic(self.root, tree, "sprint-001", "One epic")
        self.assertEqual("EP-01", self.e0["id"])
        self.assertEqual("EP-01", self.e1["id"])

    def tearDown(self):
        rm(self.root)

    def _dir(self, created):
        return os.path.basename(os.path.dirname(created["path"]))

    def test_a_repeated_epic_id_names_every_candidate(self):
        tree = board.scan(self.root)
        with self.assertRaises(HarnessError) as cm:
            board.find_epic(tree, "EP-01")
        text = str(cm.exception)
        self.assertIn("sprint-000", text)
        self.assertIn("sprint-001", text)

    def test_the_sprint_picks_one_epic_out_of_two(self):
        tree = board.scan(self.root)
        sp, ep = board.find_epic(tree, "EP-01", sprint="sprint-001")
        self.assertEqual("sprint-001", sp.id)
        self.assertEqual(self._dir(self.e1), ep.dir)

    def test_the_folder_name_identifies_one_epic(self):
        tree = board.scan(self.root)
        sp, ep = board.find_epic(tree, self._dir(self.e0))
        self.assertEqual("sprint-000", sp.id)

    def test_a_verdict_lands_in_the_sheet_of_its_own_sprint(self):
        tree = board.scan(self.root)
        t = board.new_task(self.root, tree, "Eye task", epic=self._dir(self.e1), work="S", eye="RUN")
        tree = board.scan(self.root)
        board.move(self.root, tree, t["id"], "in-progress")
        tree = board.scan(self.root)
        board.move(self.root, tree, t["id"], "done", verdict="it runs", by="user")
        tree = board.scan(self.root)
        _, mine = board.find_epic(tree, "EP-01", sprint="sprint-001")
        _, other = board.find_epic(tree, "EP-01", sprint="sprint-000")
        self.assertIn("it runs", read_text(mine.sheet))
        self.assertNotIn("it runs", read_text(other.sheet))

    def test_new_sprint_refuses_an_id_that_is_not_sprint_nnn(self):
        tree = board.scan(self.root)
        with self.assertRaises(HarnessError):
            board.new_sprint(self.root, tree, "x", "2026-09-01", "2026-09-30", sprint_id="sprint-1")

    def test_new_sprint_refuses_an_id_that_exists(self):
        tree = board.scan(self.root)
        with self.assertRaises(HarnessError):
            board.new_sprint(self.root, tree, "x", "2026-09-01", "2026-09-30", sprint_id="sprint-000")


if __name__ == "__main__":
    unittest.main()
