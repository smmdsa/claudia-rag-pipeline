"""The session pipeline: open, draft, close, the front board.

Mutation proof: see docs/MUTATION.md.
"""
import os
import unittest

from tests.helpers import cli, commit_all, make_repo, rm, seed_board

from harness import journal, manifest, session
from harness.util import HarnessError, read_text, write_text


class SessionTest(unittest.TestCase):
    def setUp(self):
        os.environ["HARNESS_TODAY"] = "2026-09-05"
        os.environ["HARNESS_NOW"] = "2026-09-05T10:00:00+00:00"
        os.environ["HARNESS_RAG_STATE_URL"] = "http://127.0.0.1:1"
        self.root = make_repo()
        seed_board(self.root)
        commit_all(self.root)

    def tearDown(self):
        for k in ("HARNESS_TODAY", "HARNESS_NOW", "HARNESS_RAG_STATE_URL"):
            os.environ.pop(k, None)
        rm(self.root)

    def test_front_rows_parse_and_number_per_brief(self):
        write_text(os.path.join(self.root, "docs", "ACTIVITY.md"),
                   "# x\n\n| front | owner | state | touched | next |\n|---|---|---|---|---|\n"
                   "| The exporter | ana | active | 2026-09-01 (abc) | ship it |\n| The login | bo | blocked | 2026-08-01 | decide |\n")
        rows = session.front_rows(self.root)
        self.assertEqual([r["front"] for r in rows], ["The exporter", "The login"])
        self.assertEqual(rows[0]["touched"].isoformat(), "2026-09-01")
        b = session.open_brief(self.root, with_rag=False)
        self.assertEqual([f["n"] for f in b["fronts"]], [1, 2])
        text = session.open_text(b)
        self.assertIn("| #1 | The exporter", text)
        self.assertIn("Numbers are per brief", text)

    def test_open_runs_init_when_not_initialised(self):
        root = make_repo(init=False)
        try:
            b = session.open_brief(root, with_rag=False)
            self.assertIn("init", b)
            self.assertTrue(manifest.exists(root))
            self.assertIn("INIT: the repository was not initialised", session.open_text(b))
        finally:
            rm(root)

    def test_open_reports_rag_broken_and_continues(self):
        b = session.open_brief(self.root, with_rag=True)
        self.assertEqual(b["rag"]["level"], "broken")
        self.assertIn("RAG: BROKEN", session.open_text(b))
        self.assertIn("NEXT: TASK-0001", session.open_text(b))

    def test_draft_then_close_needs_tldr(self):
        p = session.draft(self.root, "2026-09-05-1000")
        self.assertTrue(os.path.exists(os.path.join(self.root, p)))
        with self.assertRaises(HarnessError) as cm:
            session.close(self.root, "2026-09-05-1000", reindex=False)
        self.assertIn("TL;DR", str(cm.exception))
        with self.assertRaises(HarnessError):
            session.draft(self.root, "2026-09-05-1000")  # never overwrite

    def test_close_writes_index_journal_and_reports(self):
        p = os.path.join(self.root, session.draft(self.root, "2026-09-05-1000"))
        write_text(p, read_text(p).replace("(one sentence)", "The login works."))
        r = session.close(self.root, "2026-09-05-1000", qa_closed=["TASK-0002=ok:run"], qa_open=["TASK-0003"],
                          surprises=["the cache"], reindex=True)
        self.assertEqual(r["qa_closed"], 1)
        self.assertFalse(r["rag"]["ok"])
        log = read_text(os.path.join(self.root, "docs", "session-log.md"))
        self.assertIn("| [2026-09-05-1000](sessions/2026-09-05-1000.md) | The login works. |", log)
        last = journal.last_session(self.root)
        self.assertEqual(last["slug"], "2026-09-05-1000")
        self.assertEqual(last["qa_closed"], [{"id": "TASK-0002", "verdict": "ok", "how": "run"}])
        self.assertEqual(last["branch"], "main")
        self.assertIn("re-index FAILED", session.close_text(r))
        self.assertIn("await a verdict", session.close_text(r))

    def test_open_after_close_measures_the_delta(self):
        p = os.path.join(self.root, session.draft(self.root, "2026-09-05-1000"))
        write_text(p, read_text(p).replace("(one sentence)", "Done."))
        session.close(self.root, "2026-09-05-1000", reindex=False)
        recorded = journal.last_session(self.root)["dirty"]
        self.assertGreaterEqual(recorded, 2)  # the document, the index, the journal
        commit_all(self.root, "after close")
        write_text(os.path.join(self.root, "new.txt"), "x")
        os.environ["HARNESS_NOW"] = "2026-09-06T12:00:00+00:00"
        b = session.open_brief(self.root, with_rag=False)
        self.assertEqual(b["git"]["commits_since_close"], 1)
        self.assertEqual(b["git"]["dirty_files"], 1)
        self.assertEqual(b["git"]["dirty_delta"], 1 - recorded)
        self.assertEqual(b["elapsed_seconds"], 26 * 3600)
        self.assertIn("Closed 1 d ago", session.open_text(b))

    def test_cli_session_open_json(self):
        code, out, err = cli(self.root, "session", "open", "--no-rag", "--json")
        self.assertEqual(code, 0, err)
        self.assertIn('"fronts"', out)


if __name__ == "__main__":
    unittest.main()
