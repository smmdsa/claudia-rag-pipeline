#!/usr/bin/env python3
"""rag-agent: re-index on a timer and publish the index state as JSON.

Runs inside the container with the Python standard library. Reads the same
index.yml and index.sqlite as qmd.
  GET  /state    JSON for the canary and the board page
  GET  /health   {"status": "ok"}
  GET  /         a small HTML view of /state
  POST /update   start `qmd update`, `qmd embed`, and `qmd cleanup`, and answer now

`qmd update` writes the new chunk of a changed document and leaves the old
vector in the database. Measured on 2026-09-05: a cleanup took the index from
434 orphaned chunks (62%) to 0, and one re-index of 2 changed documents put 2
orphans back. A run with no content change added none. So the rate grows with
the edits of the day, and only a cleanup removes them. This agent runs the
cleanup when the rate passes QMD_CLEANUP_OVER, and never on a quiet day.

Freshness is NOT the age of the newest file. `MAX(documents.modified_at)` is the
mtime of the newest SOURCE file. A collection that nobody edits looks stale while
the index is current. Source A measured that on 2026-09-02: one collection reported
119 h while `qmd update` had just covered it.

The real question is "did `qmd update` cover this collection recently?". qmd answers
it per collection on every run:
    [1/3] repo-docs (**/*.md)
    Indexed: 0 new, 0 updated, 551 unchanged, 0 removed
This agent reads that line. A collection that fails prints no `Indexed:` line, keeps
its old timestamp, and goes stale. That is the alarm. `qmd update` exits 0 even when
it fails, so the exit code cannot carry this signal (law 5).
"""
import datetime as _dt
import json
import os
import re
import sqlite3
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CONFIG = os.path.join(os.environ.get("QMD_CONFIG_DIR", "/config"), "index.yml")
CACHE = os.path.join(os.environ.get("XDG_CACHE_HOME", "/data/cache"), "qmd")
INDEX = os.path.join(CACHE, "index.sqlite")
MODELS = os.path.join(CACHE, "models")
INTERVAL_S = int(os.environ.get("QMD_UPDATE_INTERVAL", "900"))
PORT = int(os.environ.get("STATE_PORT", "8411"))
STALE_AFTER_S = int(os.environ.get("QMD_STALE_AFTER", str(INTERVAL_S * 3)))
CLEANUP_OVER = float(os.environ.get("QMD_CLEANUP_OVER", "0.10"))
STARTED = time.time()

_lock = threading.Lock()
running = False
last_run = None
runs = []
syncs = {}

_HEAD = re.compile(r"^\s*\[\d+/\d+\]\s+(\S+)\s+\(")
_INDEXED = re.compile(r"^\s*Indexed:\s+(\d+) new,\s+(\d+) updated,\s+(\d+) unchanged,\s+(\d+) removed")


def now_iso():
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def qmd_version():
    try:
        with open("/opt/qmd/node_modules/@tobilu/qmd/package.json", encoding="utf-8") as fh:
            return json.load(fh).get("version")
    except (OSError, ValueError):
        return None


def parse_indexed(text, at=None):
    """Return {collection: {at, added, updated, unchanged, removed}} from a `qmd update` transcript."""
    at = at or now_iso()
    out = {}
    current = None
    for line in (text or "").replace("\r", "\n").split("\n"):
        head = _HEAD.match(line)
        if head:
            current = head.group(1)
            continue
        m = _INDEXED.match(line)
        if m and current:
            out[current] = {"at": at, "added": int(m.group(1)), "updated": int(m.group(2)),
                            "unchanged": int(m.group(3)), "removed": int(m.group(4))}
            current = None
    return out


def parse_config(path):
    """Flat parser for the collection map. Two levels, no nesting needed."""
    collections = {}
    current = None
    in_collections = False
    if not os.path.exists(path):
        return collections
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            if not line.strip() or line.strip().startswith("#"):
                continue
            if re.match(r"^collections:\s*$", line):
                in_collections = True
                continue
            if not in_collections:
                continue
            m = re.match(r"^  (\S+):\s*$", line)
            if m:
                current = m.group(1)
                collections[current] = {}
                continue
            m = re.match(r"^    (\w+):\s*(.+?)\s*$", line)
            if m and current:
                collections[current][m.group(1)] = m.group(2).strip("\"'")
    return collections


def sh(args):
    t0 = time.time()
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=3600)
        code, text = p.returncode, p.stdout + p.stderr
    except FileNotFoundError:
        code, text = 127, "executable not found: %s" % args[0]
    except subprocess.TimeoutExpired:
        code, text = 124, "timeout"
    tail = [l for l in text.replace("\r", "\n").split("\n") if l.strip()][-5:]
    return {"cmd": " ".join(args), "code": code, "ms": int((time.time() - t0) * 1000), "tail": tail, "text": text}


def reserve():
    """Take the right to run. Return False when another run holds it."""
    global running
    with _lock:
        if running:
            return False
        running = True
    return True


def run_reserved(trigger):
    """Run the steps and release the reservation. The caller must call reserve first."""
    global running, last_run
    started = now_iso()
    steps = []
    before = after = None
    try:
        up = sh(["qmd", "update"])
        # Parse before the exit code decides anything. A partial run still records
        # the collections that printed their line.
        syncs.update(parse_indexed(up.pop("text")))
        steps.append(up)
        if up["code"] == 0:
            em = sh(["qmd", "embed"])
            em.pop("text")
            steps.append(em)
            if em["code"] == 0:
                before = orphan_rate()
                if before is not None and before > CLEANUP_OVER:
                    cl = sh(["qmd", "cleanup"])
                    cl.pop("text")
                    steps.append(cl)
                    after = orphan_rate()
        # Record the run BEFORE the reservation is released. A reader that sees
        # `running: false` must never read the record of the run before this one.
        record = {"trigger": trigger, "startedAt": started, "finishedAt": now_iso(),
                  "ok": all(s["code"] == 0 for s in steps), "steps": steps,
                  "orphanRateBefore": before, "orphanRateAfter": after}
        last_run = record
        runs.insert(0, record)
        del runs[20:]
    finally:
        with _lock:
            running = False
    print("[agent] %s: ok=%s %s" % (trigger, record["ok"], " | ".join("%s %s %sms" % (s["cmd"], s["code"], s["ms"]) for s in steps)), flush=True)
    return record


def run_update(trigger):
    """Run the steps and answer with the result. The caller waits for every step."""
    if not reserve():
        return {"skipped": True, "reason": "a run is in progress"}
    return run_reserved(trigger)


def start_update(trigger):
    """Start the steps in a thread and answer at once.

    Measured on 2026-09-05: `qmd embed` took 59415 ms on this CPU, and the client of
    `POST /update` gave up at 8 s. A client that waits for the last step reads a
    healthy service as a dead one. The run continues after this answer, and
    `GET /state` carries the result in `agent.lastRun`.
    """
    if not reserve():
        return {"skipped": True, "reason": "a run is in progress"}
    threading.Thread(target=run_reserved, args=(trigger,), daemon=True).start()
    return {"started": True, "trigger": trigger, "startedAt": now_iso()}


def file_size(p):
    try:
        return os.path.getsize(p)
    except OSError:
        return 0


def count_files(d, limit=200000):
    n = 0
    stack = [d]
    while stack and n < limit:
        cur = stack.pop()
        try:
            with os.scandir(cur) as it:
                for e in it:
                    if e.name in ("node_modules", ".git"):
                        continue
                    if e.is_dir(follow_symlinks=False):
                        stack.append(e.path)
                    else:
                        n += 1
        except OSError:
            continue
    return n


def read_index():
    indexed, totals = {}, {"documents": 0, "chunks": 0, "needsEmbedding": 0, "orphanedChunks": None}
    if not os.path.exists(INDEX):
        return indexed, totals
    con = sqlite3.connect("file:%s?mode=ro" % INDEX, uri=True)
    try:
        rows = con.execute("""
            SELECT d.collection AS name, COUNT(*) AS documents, MAX(d.modified_at) AS lastModified,
                   SUM(CASE WHEN NOT EXISTS (SELECT 1 FROM content_vectors v WHERE v.hash = d.hash) THEN 1 ELSE 0 END) AS needsEmbedding,
                   (SELECT COUNT(*) FROM content_vectors v JOIN documents d2 ON d2.hash = v.hash
                     WHERE d2.collection = d.collection AND d2.active = 1) AS chunks
            FROM documents d WHERE d.active = 1 GROUP BY d.collection""").fetchall()
        for name, documents, last_modified, needs, chunks in rows:
            indexed[name] = {"documents": documents, "lastModified": last_modified,
                             "needsEmbedding": needs or 0, "chunks": chunks or 0}
        t = con.execute("""
            SELECT (SELECT COUNT(*) FROM documents WHERE active = 1),
                   (SELECT COUNT(*) FROM content_vectors),
                   (SELECT COUNT(*) FROM content_vectors v
                     WHERE NOT EXISTS (SELECT 1 FROM documents d WHERE d.hash = v.hash AND d.active = 1))""").fetchone()
        totals = {"documents": t[0], "chunks": t[1], "orphanedChunks": t[2],
                  "needsEmbedding": sum(r["needsEmbedding"] for r in indexed.values())}
    except sqlite3.Error as exc:
        totals["error"] = str(exc)
    finally:
        con.close()
    return indexed, totals


def orphan_rate():
    """Return orphaned chunks over total chunks, or None when the index cannot answer.

    A rate that nobody measured must never read as a rate of zero. That is law 7,
    and the caller must test for None before it compares.
    """
    _, totals = read_index()
    chunks, orphans = totals.get("chunks") or 0, totals.get("orphanedChunks")
    if orphans is None or chunks <= 0:
        return None
    return orphans / float(chunks)


def _age(iso):
    if not iso:
        return None
    try:
        text = iso.replace("Z", "+00:00")
        t = _dt.datetime.fromisoformat(text)
        if t.tzinfo is None:
            t = t.replace(tzinfo=_dt.timezone.utc)
        return int((_dt.datetime.now(_dt.timezone.utc) - t).total_seconds())
    except ValueError:
        return None


def read_state():
    declared = parse_config(CONFIG)
    indexed, totals = read_index()
    collections = []
    for name, c in declared.items():
        i = indexed.get(name)
        path = c.get("path", "")
        exists = os.path.exists(path)
        sync = syncs.get(name)
        sync_age = _age(sync["at"]) if sync else None
        if not exists:
            status = "path-missing"
        elif not i:
            status = "not-indexed"
        elif i["needsEmbedding"] > 0:
            status = "needs-embed"
        elif not sync:
            status = "sync-pending" if running else "never-synced"
        elif sync_age is not None and sync_age > STALE_AFTER_S:
            status = "stale"
        else:
            status = "ok"
        collections.append({
            "name": name, "path": path, "pattern": c.get("pattern", "**/*.md"), "pathExists": exists,
            "filesOnDisk": count_files(path) if exists else 0,
            "documents": i["documents"] if i else 0, "chunks": i["chunks"] if i else 0,
            "needsEmbedding": i["needsEmbedding"] if i else 0,
            "lastModified": i["lastModified"] if i else None,
            # The age of the newest source file. Report it. Never call it freshness.
            "contentAgeSeconds": _age(i["lastModified"]) if i and i["lastModified"] else None,
            "lastSyncedAt": sync["at"] if sync else None, "syncAgeSeconds": sync_age,
            "lastSync": {k: sync[k] for k in ("added", "updated", "unchanged", "removed")} if sync else None,
            "status": status,
        })
    for name, i in indexed.items():
        if name not in declared:
            collections.append({"name": name, "status": "orphan-in-index", **i})
    models = [f for f in os.listdir(MODELS)] if os.path.isdir(MODELS) else []
    models = [f for f in models if f.endswith(".gguf")]
    return {
        "generatedAt": now_iso(), "qmdVersion": qmd_version(),
        "agent": {"uptimeSeconds": int(time.time() - STARTED), "intervalSeconds": INTERVAL_S,
                  "staleAfterSeconds": STALE_AFTER_S, "running": running, "lastRun": last_run, "recentRuns": len(runs)},
        # The database file only. A VACUUM grows the write-ahead log to the size of the
        # database, so a sum reads as sudden growth.
        "index": {"path": INDEX, "bytes": file_size(INDEX), "walBytes": file_size(INDEX + "-wal"), **totals},
        "models": [{"file": f, "bytes": file_size(os.path.join(MODELS, f))} for f in models],
        "collections": collections,
        "ok": all(c["status"] == "ok" for c in collections) and (last_run["ok"] if last_run else True),
    }


def html(state):
    def age(s, unit):
        if s is None:
            return "-"
        return "%d h" % round(s / 3600) if unit == "h" else "%d min" % round(s / 60)
    rows = "".join(
        "<tr class='%s'><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
        % (c["status"], c["name"], c["status"], c.get("path", ""), c.get("filesOnDisk", ""), c.get("documents", 0),
           c.get("chunks", 0), c.get("needsEmbedding", 0), age(c.get("syncAgeSeconds"), "min"), age(c.get("contentAgeSeconds"), "h"))
        for c in state["collections"])
    idx = state["index"]
    orphan = "not measured" if idx.get("orphanedChunks") is None else idx["orphanedChunks"]
    last = state["agent"]["lastRun"]
    return ("<!doctype html><meta charset='utf-8'><title>rag state</title>"
            "<style>body{font:14px system-ui;margin:2em}table{border-collapse:collapse}td,th{border:1px solid #ccc;padding:4px 8px}"
            "tr.ok td:nth-child(2){color:#0a0}tr.path-missing td:nth-child(2),tr.never-synced td:nth-child(2){color:#c00;font-weight:bold}"
            "tr.needs-embed td:nth-child(2),tr.not-indexed td:nth-child(2),tr.stale td:nth-child(2){color:#c80}</style>"
            "<h1>index %s</h1><p>%s documents, %s chunks (%s orphaned), %.1f MB. Last run: %s. Every %d s.</p>"
            "<table><tr><th>collection</th><th>status</th><th>path</th><th>files on disk</th><th>docs</th><th>chunks</th>"
            "<th>needs embed</th><th>synced</th><th>content age</th></tr>%s</table>"
            "<form method='post' action='/update'><button>Re-index now</button></form><p><a href='/state'>JSON</a></p>"
            % ("OK" if state["ok"] else "NEEDS ATTENTION", idx.get("documents", 0), idx.get("chunks", 0), orphan,
               idx.get("bytes", 0) / 1048576.0, ("%s ok=%s" % (last["finishedAt"], last["ok"])) if last else "none yet",
               state["agent"]["intervalSeconds"], rows))


class Handler(BaseHTTPRequestHandler):
    def _send(self, body, ctype="application/json", code=200):
        raw = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype + ("; charset=utf-8" if ctype.startswith("text/") else ""))
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path == "/health":
            self._send(json.dumps({"status": "ok", "running": running}))
        elif self.path == "/state":
            self._send(json.dumps(read_state()))
        elif self.path == "/":
            self._send(html(read_state()), "text/html")
        else:
            self._send("not found", "text/plain", 404)

    def do_POST(self):
        if self.path == "/update":
            # Answer before the steps run. A 60 second embed must not time out a client.
            self._send(json.dumps(start_update("http")))
        else:
            self._send("not found", "text/plain", 404)

    def log_message(self, *args):
        pass


def main():
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print("[agent] state on :%d, update every %d s, index %s" % (PORT, INTERVAL_S, INDEX), flush=True)
    run_update("startup")
    while True:
        time.sleep(INTERVAL_S)
        run_update("timer")


if __name__ == "__main__":
    main()
