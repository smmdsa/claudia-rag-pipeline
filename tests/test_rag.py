"""The RAG canary against a fixture state server, and the agent parsers.

The canary reports the health of the search index. A canary that sings when nothing
is wrong trains the reader to skip it, so the quiet cases are tested as hard as the
loud ones. No container is needed: the suite serves its own /state.

Mutation proof (docs/MUTATION.md): M07 (never-synced as warning) 1 red; M08 (Indexed line without header) 0 red until the fixture got a total line, then 1 red.
"""
import importlib.util
import json
import os
import sys
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from tests.helpers import PRODUCT, make_repo, rm

from harness import profile, rag, session
from harness.util import read_text


def close_result(rag_result):
    """The smallest `session.close` result that `close_text` reads."""
    return {"doc": "docs/sessions/x.md", "log": "docs/session-log.md", "journal": {},
            "observations": 0, "rag": rag_result, "awaiting_verdict": 0, "qa_closed": 0}

STATE = {}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps(STATE if self.path == "/state" else {"status": "ok"}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        body = json.dumps({"trigger": "http", "ok": True}).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def collection(name, docs=100, **over):
    row = {"name": name, "path": "/src/" + name, "pattern": "**/*.md", "pathExists": True, "filesOnDisk": docs,
           "documents": docs, "chunks": docs * 8, "needsEmbedding": 0, "lastModified": "2026-09-02T16:09:03Z",
           "contentAgeSeconds": 1895, "lastSyncedAt": "2026-09-02T16:40:00Z", "syncAgeSeconds": 4,
           "lastSync": {"added": 0, "updated": 0, "unchanged": docs, "removed": 0}, "status": "ok"}
    row.update(over)
    return row


def state(collections=None, **index_over):
    idx = {"documents": 2267, "chunks": 12039, "orphanedChunks": 260, "bytes": 111144640, "needsEmbedding": 0}
    idx.update(index_over)
    return {"generatedAt": "2026-09-02T16:40:38Z", "qmdVersion": "2.8.3",
            "agent": {"uptimeSeconds": 1917, "intervalSeconds": 900, "staleAfterSeconds": 2700, "running": False,
                      "lastRun": {"ok": True}, "recentRuns": 4},
            "index": idx,
            "collections": collections if collections is not None else [collection("repo-docs", 551), collection("memory", 67)],
            "ok": True}


class RagCanaryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = HTTPServer(("127.0.0.1", 0), Handler)
        cls.base = "http://127.0.0.1:%d" % cls.srv.server_port
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def canary(self, st):
        global STATE
        STATE = st
        return rag.health(None, url=self.base, mcp=self.base)

    def test_all_healthy_is_quiet(self):
        r = self.canary(state())
        self.assertEqual((r["level"], r["exit"]), ("ok", 0))
        self.assertEqual(r["warnings"], [])
        text = rag.health_text(r)
        self.assertIn("RAG: OK", text)
        self.assertIn("orphaned 260 (2%)", text)
        self.assertIn("synced 0 min", text)

    def test_old_content_with_fresh_sync_is_healthy(self):
        # THE regression. The old canary read the file date and called it freshness.
        r = self.canary(state([collection("repo-docs", 433, contentAgeSeconds=864000, syncAgeSeconds=4)]))
        self.assertEqual(r["exit"], 0)
        self.assertIn("content 10 d", rag.health_text(r))

    def test_stale_sync_names_collection_and_limit(self):
        r = self.canary(state([collection("memory", 67, syncAgeSeconds=7200, status="stale")]))
        self.assertEqual((r["level"], r["exit"]), ("warnings", 1))
        self.assertIn("`memory` went 2 h", r["warnings"][0])
        self.assertIn("45 min", r["warnings"][0])

    def test_never_synced_is_broken(self):
        r = self.canary(state([collection("memory", 67, syncAgeSeconds=None, lastSyncedAt=None, status="never-synced")]))
        self.assertEqual(r["exit"], 2)
        self.assertIn("exits 0 on error", r["problems"][0])

    def test_first_sync_is_a_warning(self):
        r = self.canary(state([collection("memory", 67, syncAgeSeconds=None, status="sync-pending")]))
        self.assertEqual(r["exit"], 1)

    def test_orphans_over_limit(self):
        r = self.canary(state(orphanedChunks=6140))
        self.assertEqual(r["exit"], 1)
        self.assertIn("51%", r["warnings"][0])

    def test_missing_orphan_count_is_not_measured_never_zero(self):
        s = state()
        del s["index"]["orphanedChunks"]
        r = self.canary(s)
        self.assertEqual(r["exit"], 0)
        self.assertIn("orphaned not measured", rag.health_text(r))
        self.assertNotIn("orphaned 0", rag.health_text(r))

    def test_path_missing_is_broken(self):
        r = self.canary(state([collection("memory", 67, pathExists=False, status="path-missing")]))
        self.assertEqual(r["exit"], 2)
        self.assertIn("does not exist in the container", r["problems"][0])

    def test_no_collections_is_broken(self):
        r = self.canary(state([]))
        self.assertEqual(r["exit"], 2)
        self.assertIn("no collection", r["problems"][0])

    def test_state_down_is_broken(self):
        r = rag.health(None, url="http://127.0.0.1:1", mcp="http://127.0.0.1:1")
        self.assertEqual(r["exit"], 2)
        self.assertIn("does not answer", r["problems"][0])

    def test_update_request(self):
        self.assertTrue(rag.request_update(url=self.base)["ok"])
        self.assertFalse(rag.request_update(url="http://127.0.0.1:1")["ok"])


SLOW_S = 1.5


class SlowHandler(BaseHTTPRequestHandler):
    """A service that takes the request and answers late. It is healthy, not dead."""

    def do_POST(self):
        time.sleep(SLOW_S)
        body = b'{"started": true}'
        try:
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except OSError:
            pass  # the client timed out and closed. That is the case under test.

    def log_message(self, *args):
        pass


class SkipHandler(BaseHTTPRequestHandler):
    """A service that already runs. It answers at once and refuses a second run."""

    def do_POST(self):
        body = json.dumps({"skipped": True, "reason": "a run is in progress"}).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class UpdateReportTest(unittest.TestCase):
    """THE regression of TASK-0013.

    On 2026-09-05 `session close` printed "the state service did not answer" while the
    service answered every GET in 0.03 s. `qmd embed` took 59415 ms and the client gave
    up at 8 s. A timeout and a refused connection produced the same word.
    """

    DEAD = "http://127.0.0.1:1"  # port 1 holds no service on any machine

    @classmethod
    def setUpClass(cls):
        cls.slow = HTTPServer(("127.0.0.1", 0), SlowHandler)
        cls.slow_url = "http://127.0.0.1:%d" % cls.slow.server_port
        threading.Thread(target=cls.slow.serve_forever, daemon=True).start()
        cls.busy = HTTPServer(("127.0.0.1", 0), SkipHandler)
        cls.busy_url = "http://127.0.0.1:%d" % cls.busy.server_port
        threading.Thread(target=cls.busy.serve_forever, daemon=True).start()
        cls.fast = HTTPServer(("127.0.0.1", 0), Handler)
        cls.fast_url = "http://127.0.0.1:%d" % cls.fast.server_port
        threading.Thread(target=cls.fast.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        for srv in (cls.slow, cls.busy, cls.fast):
            srv.shutdown()
            srv.server_close()

    def test_http_json_names_a_timeout_and_a_refusal_apart(self):
        data, reason = rag.http_json(self.slow_url + "/update", method="POST", timeout=0.2)
        self.assertIsNone(data)
        self.assertEqual(reason, "timeout")
        data, reason = rag.http_json(self.DEAD + "/update", method="POST", timeout=2)
        self.assertIsNone(data)
        self.assertEqual(reason, "refused")

    def test_a_slow_answer_is_not_a_dead_service(self):
        r = rag.request_update(url=self.slow_url, timeout=0.2)
        self.assertEqual(r["reason"], "timeout")
        self.assertTrue(r["ok"])  # the request arrived, so the re-index started
        self.assertIn("started", r["note"])
        self.assertIn("rag health", r["note"])
        self.assertNotIn("The stack is down", r["note"])

    def test_a_refused_connection_is_a_dead_service(self):
        r = rag.request_update(url=self.DEAD, timeout=2)
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], "refused")
        self.assertIn("refused", r["note"])
        self.assertIn("The stack is down", r["note"])

    def test_a_healthy_stack_reports_started(self):
        r = rag.request_update(url=self.fast_url)
        self.assertEqual((r["ok"], r["reason"], r["note"]), (True, None, "started"))
        self.assertIn("- RAG: re-index started", session.close_text(close_result(r)))

    def test_a_timeout_reaches_the_close_line_and_never_says_FAILED(self):
        r = rag.request_update(url=self.slow_url, timeout=0.2)
        text = session.close_text(close_result(r))
        self.assertIn("re-index started", text)
        self.assertNotIn("FAILED", text)

    def test_a_run_in_progress_is_not_an_error(self):
        r = rag.request_update(url=self.busy_url)
        self.assertTrue(r["ok"])
        self.assertIn("a run is in progress", r["note"])

    def test_the_canary_names_why_the_state_did_not_answer(self):
        r = rag.health(None, url=self.DEAD, mcp=self.DEAD)
        self.assertEqual(r["exit"], 2)
        self.assertIn("refused", r["problems"][0])


def load_agent():
    path = os.path.join(PRODUCT, "harness", "templates", "infra", "rag", "agent", "agent.py")
    spec = importlib.util.spec_from_file_location("rag_agent", path)
    mod = importlib.util.module_from_spec(spec)
    before = sys.dont_write_bytecode
    sys.dont_write_bytecode = True  # a .pyc under templates/ would be installed as a file
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.dont_write_bytecode = before
    return mod


class AgentParserTest(unittest.TestCase):
    def test_parse_indexed_reads_per_collection_lines(self):
        agent = load_agent()
        # The last line is a total with no collection header. A parser that reads an
        # `Indexed:` line without its header records it under no name. Mutation M08
        # (drop the `current` guard) stayed green until this line existed.
        text = ("[1/3] repo-docs (**/*.md)\nScanning...\nIndexed: 2 new, 1 updated, 548 unchanged, 0 removed\n"
                "[2/3] repo-code (**/*.py)\nerror: ENOENT\n[3/3] memory (**/*.md)\r\nIndexed: 0 new, 0 updated, 65 unchanged, 1 removed\n"
                "Indexed: 2 new, 1 updated, 613 unchanged, 1 removed\n")
        out = agent.parse_indexed(text, at="2026-09-04T00:00:00+00:00")
        self.assertNotIn(None, out)
        self.assertEqual(sorted(out), ["memory", "repo-docs"])
        self.assertEqual(out["memory"]["unchanged"], 65)  # not the total of 613
        self.assertEqual(out["repo-docs"]["added"], 2)
        self.assertEqual(out["memory"]["removed"], 1)
        self.assertNotIn("repo-code", out)  # no Indexed line: the alarm
        self.assertEqual(agent.parse_indexed(""), {})

    def test_parse_config(self):
        agent = load_agent()
        root = make_repo()
        try:
            cols = agent.parse_config(os.path.join(root, "infra", "rag", "config", "index.yml"))
            self.assertEqual(cols["repo-docs"]["path"], "/src/repo")
            self.assertEqual(cols["memory"]["pattern"], "**/*.md")
        finally:
            rm(root)


def fake_agent(totals, codes=None):
    """Load the agent, and replace `sh` and `read_index` with fakes.

    `totals` is a list. Each call of `read_index` takes the next entry, so a test
    can measure the rate before the cleanup and after it.
    """
    agent = load_agent()
    calls = []
    left = list(totals)

    def fake_sh(args):
        calls.append(" ".join(args))
        code = (codes or {}).get(args[1], 0)
        return {"cmd": " ".join(args), "code": code, "ms": 1, "tail": [], "text": ""}

    agent.sh = fake_sh
    agent.read_index = lambda: ({}, left.pop(0) if len(left) > 1 else left[0])
    return agent, calls


class AgentCleanupTest(unittest.TestCase):
    """`qmd update` leaves the old vector of a changed document behind.

    Measured on 2026-09-05: a cleanup took the index from 434 orphaned chunks (62%)
    to 0, and one re-index of 2 changed documents put 2 back. So the agent runs the
    cleanup itself, and only when the rate passes the threshold.
    """

    agent_with = staticmethod(fake_agent)

    def test_cleanup_runs_when_the_rate_passes_the_threshold(self):
        agent, calls = self.agent_with([{"chunks": 696, "orphanedChunks": 434},
                                        {"chunks": 262, "orphanedChunks": 0}])
        run = agent.run_update("test")
        self.assertEqual(calls, ["qmd update", "qmd embed", "qmd cleanup"])
        self.assertEqual([s["cmd"] for s in run["steps"]],
                         ["qmd update", "qmd embed", "qmd cleanup"])
        self.assertAlmostEqual(run["orphanRateBefore"], 434 / 696.0)
        self.assertEqual(run["orphanRateAfter"], 0.0)

    def test_a_quiet_day_costs_no_cleanup(self):
        # 2 of 264 is 0.7%, under the 10% threshold. This is the state right after a
        # cleanup, and the agent must not vacuum the database every 900 seconds.
        agent, calls = self.agent_with([{"chunks": 264, "orphanedChunks": 2}])
        run = agent.run_update("test")
        self.assertEqual(calls, ["qmd update", "qmd embed"])
        self.assertIsNone(run["orphanRateAfter"])

    def test_a_rate_that_nobody_measured_is_not_a_rate_of_zero(self):
        # law 7: a default value must never look like a measurement. An index that
        # cannot answer must not read as a clean index, and must not read as a dirty
        # one either. The agent measures nothing and cleans nothing.
        agent, calls = self.agent_with([{"chunks": 0, "orphanedChunks": None}])
        run = agent.run_update("test")
        self.assertEqual(calls, ["qmd update", "qmd embed"])
        self.assertIsNone(run["orphanRateBefore"])

    def test_an_empty_index_never_divides_by_zero(self):
        agent, _ = self.agent_with([{"chunks": 0, "orphanedChunks": 0}])
        self.assertIsNone(agent.orphan_rate())

    def test_a_failed_embed_stops_before_the_cleanup(self):
        # A cleanup after a failed embed removes the vectors that the embed did not
        # write yet. The rate is high for that reason, and the cleanup is wrong.
        agent, calls = self.agent_with([{"chunks": 696, "orphanedChunks": 434}],
                                       codes={"embed": 1})
        run = agent.run_update("test")
        self.assertEqual(calls, ["qmd update", "qmd embed"])
        self.assertFalse(run["ok"])

    def test_a_failed_update_stops_before_both(self):
        agent, calls = self.agent_with([{"chunks": 696, "orphanedChunks": 434}],
                                       codes={"update": 1})
        agent.run_update("test")
        self.assertEqual(calls, ["qmd update"])


class AgentStartUpdateTest(unittest.TestCase):
    """`POST /update` must answer before the steps run.

    Measured on 2026-09-05: `qmd embed` took 59415 ms and the client gave up at 8 s.
    The endpoint that answers last cannot be reached by a client that waits.
    """

    def slow_agent(self, seconds=1.5):
        agent, calls = fake_agent([{"chunks": 264, "orphanedChunks": 2}])
        inner = agent.sh
        started = threading.Event()

        def slow_sh(args):
            started.set()
            time.sleep(seconds)
            return inner(args)

        agent.sh = slow_sh
        return agent, calls, started

    def test_start_update_answers_before_the_steps_finish(self):
        agent, calls, started = self.slow_agent()
        t0 = time.time()
        answer = agent.start_update("http")
        elapsed = time.time() - t0
        self.assertTrue(answer["started"])
        self.assertLess(elapsed, 0.5)  # the first step alone takes 1.5 s
        self.assertTrue(started.wait(2))
        self.assertTrue(agent.running)  # the run holds the reservation
        self.assertIsNone(agent.last_run)  # and has written no record yet

    def test_a_second_start_never_runs_two_updates_at_once(self):
        agent, calls, started = self.slow_agent()
        self.assertTrue(agent.start_update("http")["started"])
        self.assertTrue(started.wait(2))
        second = agent.start_update("http")
        self.assertTrue(second["skipped"])
        self.assertEqual(second["reason"], "a run is in progress")
        self.assertNotIn("started", second)

    def test_the_record_lands_before_the_reservation_is_released(self):
        # A reader that sees `running: false` must never read the record of the run
        # before this one. `runs.insert` reports the state at the moment of the write,
        # so a release that happens first turns this red with no sleep and no race.
        agent, calls = fake_agent([{"chunks": 264, "orphanedChunks": 2}])
        seen = []

        class Watch(list):
            def insert(self, i, item):
                seen.append({"running": agent.running, "recorded": agent.last_run is not None})
                list.insert(self, i, item)

        agent.runs = Watch()
        agent.run_update("test")
        self.assertEqual(seen, [{"running": True, "recorded": True}])
        self.assertFalse(agent.running)
        self.assertEqual(calls, ["qmd update", "qmd embed"])

    def test_run_update_still_answers_with_the_result(self):
        # The timer and the startup call keep the synchronous form.
        agent, calls = fake_agent([{"chunks": 264, "orphanedChunks": 2}])
        run = agent.run_update("timer")
        self.assertEqual(run["trigger"], "timer")
        self.assertTrue(run["ok"])
        self.assertFalse(agent.running)


class RagConfigTest(unittest.TestCase):
    def test_write_config_from_profile(self):
        root = make_repo()
        try:
            profile.set_values(root, [("languages", "python, typescript"), ("purpose", "sells \"things\"")])
            r = rag.write_config(root)
            self.assertEqual(r["collections"], ["repo-docs", "repo-code", "memory"])
            text = read_text(os.path.join(root, "infra", "rag", "config", "index.yml"))
            self.assertIn("**/*.{py,ts,tsx}", text)
            self.assertNotIn('""', text.split("global_context")[1].split("\n")[0])
        finally:
            rm(root)


if __name__ == "__main__":
    unittest.main()
