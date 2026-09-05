"""The board page: the SQLite cache, the static page, the server.

Mutation proof (docs/MUTATION.md): M14 (unmeasured age stored as 0) 1 red; M04 (days off by one) 1 red here;
M43 (the cache is never stale) 2 red.
"""
import json
import os
import sqlite3
import threading
import unittest
import urllib.request

from tests.helpers import make_repo, rm, seed_board

from harness import board, dashboard
from harness.ports import is_free
from harness.util import read_text


class DashboardTest(unittest.TestCase):
    def setUp(self):
        os.environ["HARNESS_TODAY"] = "2026-09-05"
        self.root = make_repo()
        self.ids = seed_board(self.root)
        tree = board.scan(self.root)
        board.move(self.root, tree, self.ids["t2"], "in-progress")

    def tearDown(self):
        os.environ.pop("HARNESS_TODAY", None)
        rm(self.root)

    def test_build_db_is_a_cache_with_built_at(self):
        r = dashboard.build_db(self.root)
        self.assertEqual(r["tasks"], 3)
        con = sqlite3.connect(dashboard.db_path(self.root))
        meta = dict(con.execute("SELECT key, value FROM meta"))
        self.assertIn("built_at", meta)
        self.assertIn("cache", meta["note"])
        rows = con.execute("SELECT id, state, state_age_days FROM tasks ORDER BY id").fetchall()
        self.assertEqual(rows[1][1], "in-progress")
        self.assertIsNone(rows[1][2])  # not committed: not measured, never 0
        self.assertIn("CACHE ONLY", dashboard.SCHEMA)
        con.close()

    def test_static_page_carries_data_and_age(self):
        out = os.path.join(self.root, "board.html")
        r = dashboard.static(self.root, out)
        text = read_text(out)
        self.assertIn('"TASK-0002"', text)
        self.assertIn(r["built_at"], text)
        self.assertIn("the folder tree under work/ is the truth", text)
        self.assertNotIn("__BOARD_JSON__", text)

    def test_serve_answers_health_and_board(self):
        port = 18412
        while not is_free(port):
            port += 1
        t = threading.Thread(target=dashboard.serve, kwargs={"root": self.root, "port": port, "once": True}, daemon=True)
        t.start()
        for _ in range(50):
            try:
                body = urllib.request.urlopen("http://127.0.0.1:%d/api/board" % port, timeout=2).read()
                break
            except OSError:
                import time
                time.sleep(0.1)
        data = json.loads(body)
        self.assertEqual(len(data["tasks"]), 3)
        self.assertEqual(data["sprints"][0]["days_remaining"], 9)

    def test_a_move_makes_the_cache_stale(self):
        dashboard.build_db(self.root)
        db = dashboard.db_path(self.root)
        self.assertFalse(dashboard.is_stale(self.root, db))
        tree = board.scan(self.root)
        board.move(self.root, tree, self.ids["t2"], "done", verdict="seen", by="user")
        self.assertTrue(dashboard.is_stale(self.root, db))

    def test_a_missing_cache_is_stale(self):
        self.assertTrue(dashboard.is_stale(self.root, os.path.join(self.root, "nothing.sqlite")))

    def test_the_page_reads_a_move_with_no_wait(self):
        """The tree is the truth. The page must never answer from an old reading."""
        port = 18512
        while not is_free(port):
            port += 1
        threading.Thread(target=dashboard.serve,
                         kwargs={"root": self.root, "port": port, "once": False},
                         daemon=True).start()
        for _ in range(50):
            try:
                urllib.request.urlopen("http://127.0.0.1:%d/health" % port, timeout=2).read()
                break
            except OSError:
                import time
                time.sleep(0.1)
        tree = board.scan(self.root)
        board.move(self.root, tree, self.ids["t2"], "done", verdict="seen", by="user")
        body = urllib.request.urlopen("http://127.0.0.1:%d/api/board" % port, timeout=5).read()
        states = {t["id"]: t["state"] for t in json.loads(body)["tasks"]}
        self.assertEqual(states[self.ids["t2"]], "done")

    def test_an_unchanged_tree_runs_no_rebuild(self):
        """A rebuild on every request would read the whole tree for every reader."""
        db = dashboard.db_path(self.root)
        dashboard.build_db(self.root, db)
        calls = []
        real = dashboard.build_db
        dashboard.build_db = lambda *a, **k: calls.append(1)
        try:
            dashboard.refresh(self.root, db)
            dashboard.refresh(self.root, db)
        finally:
            dashboard.build_db = real
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
