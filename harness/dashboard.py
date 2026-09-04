"""The board dashboard: a SQLite cache, an http.server, and a static page.

The SQLite database is a CACHE and never the source of truth. `build_db` reads the
folder tree and writes the database. A reader of the database sees `built_at` and
knows the age of what they read. The tree stays the truth.
"""
import datetime as _dt
import html
import json
import os
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from harness import VERSION, state
from harness.board import all_tasks, scan
from harness.clock import days_remaining, sprint_status
from harness.ports import is_free, port_for
from harness.util import HarnessError, now, now_iso, read_text, today

DB = os.path.join(".harness", "board.sqlite")
TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard.html")

SCHEMA = """
-- CACHE ONLY. The folder tree under work/ is the source of truth.
-- `python3 -m harness dashboard build-db` rewrites every table from the tree.
-- Nothing writes here except that command. A row here is a copy, not a fact.
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE sprints (id TEXT PRIMARY KEY, title TEXT, starts TEXT, ends TEXT,
                      status TEXT, days_remaining INTEGER, ord INTEGER);
CREATE TABLE epics (id TEXT, sprint TEXT, title TEXT, ord INTEGER, PRIMARY KEY (sprint, id));
CREATE TABLE tasks (id TEXT PRIMARY KEY, title TEXT, work TEXT, eye TEXT, owner TEXT,
                    due TEXT, priority INTEGER, state TEXT, sprint TEXT, epic TEXT,
                    path TEXT, has_verdict INTEGER, needs_decision TEXT,
                    -- age in days since the task entered its state folder, from git. NULL = not measured.
                    state_age_days REAL);
"""


def db_path(root):
    return os.path.join(root, DB)


def build_db(root, path=None):
    path = path or db_path(root)
    tree = scan(root)
    tmp = path + ".tmp"
    if os.path.exists(tmp):
        os.remove(tmp)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    con = sqlite3.connect(tmp)
    con.executescript(SCHEMA)
    con.execute("INSERT INTO meta VALUES ('built_at', ?)", (now_iso(),))
    con.execute("INSERT INTO meta VALUES ('harness_version', ?)", (VERSION,))
    con.execute("INSERT INTO meta VALUES ('root', ?)", (root,))
    con.execute("INSERT INTO meta VALUES ('note', 'cache of the folder tree. The tree is the truth.')")
    for sp in tree.sprints:
        con.execute("INSERT INTO sprints VALUES (?,?,?,?,?,?,?)",
                    (sp.id, sp.title, sp.starts or None, sp.ends or None, sprint_status(sp), days_remaining(sp), sp.order))
        for e in sp.epics:
            con.execute("INSERT INTO epics VALUES (?,?,?,?)", (e.id, sp.id, e.title, e.order))
    for t in all_tasks(tree):
        entered = state._entered_at(root, t.path)
        age = round((now().timestamp() - entered) / 86400.0, 1) if entered else None
        con.execute("INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (t.id, t.title, t.work, t.eye, t.owner, t.due or None, t.priority, t.state,
                     t.sprint or None, t.epic or None, os.path.relpath(t.path, root), int(t.has_verdict()),
                     t.decision or None, age))
    con.commit()
    con.close()
    os.replace(tmp, path)
    return {"db": os.path.relpath(path, root), "tasks": len(all_tasks(tree)), "sprints": len(tree.sprints)}


def read_db(path):
    if not os.path.exists(path):
        raise HarnessError("%s does not exist. Run `python3 -m harness dashboard build-db`." % path)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    meta = {r["key"]: r["value"] for r in con.execute("SELECT key, value FROM meta")}
    sprints = [dict(r) for r in con.execute("SELECT * FROM sprints ORDER BY ord")]
    epics = [dict(r) for r in con.execute("SELECT * FROM epics ORDER BY sprint, ord")]
    tasks = [dict(r) for r in con.execute("SELECT * FROM tasks ORDER BY id")]
    con.close()
    return {"meta": meta, "sprints": sprints, "epics": epics, "tasks": tasks, "today": today().isoformat()}


def render_html(data):
    payload = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
    return read_text(TEMPLATE).replace("__BOARD_JSON__", payload)


def static(root, out, db=None):
    if db is None or not os.path.exists(db or db_path(root)):
        build_db(root)
    data = read_db(db or db_path(root))
    text = render_html(data)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(text)
    return {"out": out, "bytes": len(text.encode("utf-8")), "built_at": data["meta"].get("built_at")}


class Handler(BaseHTTPRequestHandler):
    root = None
    db = None

    def _send(self, body, ctype="text/html; charset=utf-8", code=200):
        raw = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        try:
            if self.path == "/health":
                self._send(json.dumps({"status": "ok", "db": os.path.exists(self.db)}), "application/json")
            elif self.path == "/api/board":
                self._send(json.dumps(read_db(self.db), ensure_ascii=False), "application/json")
            elif self.path == "/":
                self._send(render_html(read_db(self.db)))
            else:
                self._send("not found", "text/plain", 404)
        except HarnessError as exc:
            self._send(str(exc), "text/plain", 503)

    def do_POST(self):
        if self.path == "/rebuild":
            r = build_db(self.root, self.db)
            self._send(json.dumps(r), "application/json")
        else:
            self._send("not found", "text/plain", 404)

    def log_message(self, *args):
        pass


def serve(root, port=None, host="127.0.0.1", rebuild_every=0, db=None, once=False):
    port = port or port_for("HARNESS_BOARD_PORT")
    db = db or db_path(root)
    if not is_free(port, host):
        raise HarnessError("port %d is taken. Override it with HARNESS_BOARD_PORT=<port>. Run `python3 -m harness ports`." % port)
    build_db(root, db)
    Handler.root, Handler.db = root, db
    server = ThreadingHTTPServer((host, port), Handler)
    if rebuild_every:
        def loop():
            while True:
                time.sleep(rebuild_every)
                try:
                    build_db(root, db)
                except Exception as exc:  # the server keeps serving the old cache
                    print("dashboard: rebuild failed: %s" % exc, flush=True)
        threading.Thread(target=loop, daemon=True).start()
    print("dashboard: http://%s:%d/  cache %s%s" % (host, port, db, (" rebuilt every %ds" % rebuild_every) if rebuild_every else ""), flush=True)
    if once:
        server.handle_request()
    else:
        server.serve_forever()
    return server
