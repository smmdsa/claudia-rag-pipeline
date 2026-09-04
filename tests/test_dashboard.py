"""The board page: the SQLite cache, the static page, the server.

Mutation proof: see docs/MUTATION.md.
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


if __name__ == "__main__":
    unittest.main()
