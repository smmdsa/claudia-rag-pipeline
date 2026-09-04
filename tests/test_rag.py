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
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from tests.helpers import PRODUCT, make_repo, rm

from harness import profile, rag
from harness.util import read_text

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
