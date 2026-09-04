"""The RAG canary and the index configuration.

The canary reads `/state` from the companion service and measures the LIVE index:
the last time `qmd update` covered each collection, the documents with no vector,
and the orphaned chunks. It never reads a file date. A path that exists does not
prove that the index is correct. A missing count prints `not measured`, never 0.

Exit codes: 0 ok, 1 warnings, 2 broken.
"""
import json
import os
import urllib.error
import urllib.request

from harness import manifest, profile
from harness.ports import port_for
from harness.util import human_delta, write_text

CONFIG = os.path.join("infra", "rag", "config", "index.yml")
ORPHAN_WARN_PCT = 20


def state_url():
    return os.environ.get("HARNESS_RAG_STATE_URL") or "http://127.0.0.1:%d" % port_for("HARNESS_RAG_STATE_PORT")


def mcp_url():
    return os.environ.get("HARNESS_RAG_MCP_URL") or "http://127.0.0.1:%d" % port_for("HARNESS_RAG_PORT")


def http_json(url, method="GET", timeout=4):
    req = urllib.request.Request(url, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
    except (urllib.error.URLError, OSError, ValueError):
        return None
    try:
        return json.loads(body)
    except ValueError:
        return None


def request_update(root=None, url=None):
    data = http_json((url or state_url()) + "/update", method="POST", timeout=8)
    if data is None:
        return {"ok": False, "note": "the state service at %s did not answer" % (url or state_url())}
    return {"ok": True, "note": "started" if not data.get("skipped") else data.get("reason", "skipped"), "data": data}


def health(root=None, url=None, mcp=None):
    url = url or state_url()
    mcp = mcp or mcp_url()
    report = {"level": "ok", "problems": [], "warnings": [], "collections": [], "index": {}, "state_url": url}

    def broken(msg):
        report["level"] = "broken"
        report["problems"].append(msg)

    def warn(msg):
        if report["level"] == "ok":
            report["level"] = "warnings"
        report["warnings"].append(msg)

    st = http_json(url + "/state", timeout=6)
    if st is None:
        broken("the index state at %s does not answer. The stack is down, or another port is set. "
               "Start it with `infra/rag/up.sh`, or check `python3 -m harness ports`." % url)
        report["exit"] = 2
        return report
    if http_json(mcp + "/health", timeout=4) is None:
        broken("the MCP server at %s does not answer. Searches fail. Check `infra/rag/up.sh logs rag`." % mcp)
    idx = st.get("index") or {}
    agent = st.get("agent") or {}
    report["index"] = {
        "documents": idx.get("documents"), "chunks": idx.get("chunks"), "bytes": idx.get("bytes"),
        "needs_embedding": idx.get("needsEmbedding"),
        "orphaned": idx.get("orphanedChunks") if isinstance(idx.get("orphanedChunks"), int) else None,
        "last_run_ok": (agent.get("lastRun") or {}).get("ok"),
    }
    orphaned, chunks = report["index"]["orphaned"], idx.get("chunks") or 0
    if orphaned is not None and chunks:
        pct = int(round(100.0 * orphaned / chunks))
        report["index"]["orphaned_pct"] = pct
        if pct >= ORPHAN_WARN_PCT:
            warn("%d%% of the index is orphaned chunks. The search weighs more than it answers. Run `qmd cleanup` in the container." % pct)
    cols = st.get("collections") or []
    if not cols:
        broken("the container declares no collection. Every search returns nothing without an error. "
               "Check the config mount: `infra/rag/up.sh up -d --force-recreate`.")
    stale_after = agent.get("staleAfterSeconds")
    for c in cols:
        status = c.get("status")
        row = {"name": c.get("name"), "path": c.get("path"), "exists": bool(c.get("pathExists")),
               "documents": c.get("documents"), "needs_embedding": c.get("needsEmbedding"),
               "synced": human_delta(c.get("syncAgeSeconds")), "content_age": human_delta(c.get("contentAgeSeconds")),
               "status": status}
        report["collections"].append(row)
        name = row["name"]
        if status == "path-missing" or not row["exists"]:
            broken("the collection `%s` mounts %s, and that path does not exist in the container. Check infra/rag/docker-compose.yml." % (name, row["path"]))
        elif status == "never-synced":
            broken("`%s` was never covered by `qmd update` since the agent started. `qmd update` exits 0 on error, so only this record proves it. Read `infra/rag/up.sh logs -f rag-agent`." % name)
        elif status == "sync-pending":
            warn("`%s` is in its first sync. The agent just started. Ask again in a minute." % name)
        elif status == "stale":
            warn("`%s` went %s without `qmd update`, and the limit is %s. Read `infra/rag/up.sh logs -f rag-agent`."
                 % (name, row["synced"], human_delta(stale_after)))
        elif status == "needs-embed":
            warn("`%s` has %s document(s) with no vector. The semantic search does not see them." % (name, row["needs_embedding"]))
        elif status == "not-indexed":
            warn("`%s` is declared and not indexed yet." % name)
        elif status == "orphan-in-index":
            warn("`%s` is in the index and not in the config." % name)
        elif status not in ("ok", None):
            warn("`%s` is in state `%s`." % (name, status))
    if report["index"]["last_run_ok"] is False:
        warn("the last index run failed. Read `infra/rag/up.sh logs -f rag-agent`.")
    report["exit"] = {"ok": 0, "warnings": 1, "broken": 2}[report["level"]]
    return report


def health_text(r):
    lines = [{"ok": "RAG: OK", "warnings": "RAG: warnings", "broken": "RAG: BROKEN"}[r["level"]]]
    for p in r["problems"]:
        lines.append("  [X] " + p)
    for w in r["warnings"]:
        lines.append("  [!] " + w)
    i = r.get("index") or {}
    if i:
        orphan = "not measured" if i.get("orphaned") is None else "%s (%s%%)" % (i["orphaned"], i.get("orphaned_pct", "?"))
        lines.append("  index: %s documents, %s chunks, %s pending vectors, orphaned %s"
                     % (i.get("documents", "?"), i.get("chunks", "?"), i.get("needs_embedding", "?"), orphan))
    for c in r["collections"]:
        mark = "ok " if c["status"] == "ok" else "!! "
        lines.append("  [%s] %-14s %6s docs  synced %-8s content %-8s %s"
                     % (mark, c["name"], c["documents"] if c["documents"] is not None else "?", c["synced"], c["content_age"], c["path"]))
    return "\n".join(lines)


def write_config(root):
    """Write infra/rag/config/index.yml from the profile. Container paths only."""
    data = manifest.load(root) or {}
    prof = data.get("profile") or {}
    patterns = profile.code_patterns(prof)
    project = data.get("project") or os.path.basename(os.path.realpath(root))
    lines = [
        "# Collections that the container indexes. Paths are CONTAINER paths and do not",
        "# change between machines. docker-compose.yml maps the host paths from",
        "# .harness/env.local onto them. `python3 -m harness rag config` regenerates this file",
        "# from the project profile.",
        'global_context: "%s: %s"' % (project, (prof.get("purpose") or "project documents, code, and durable memories").replace('"', "'")),
        "",
        "collections:",
        "  repo-docs:",
        "    path: /src/repo",
        '    pattern: "**/*.md"',
        "    ignore:",
        '      - "**/node_modules/**"',
        '      - "**/dist/**"',
        '      - "**/vendor/**"',
        '      - "**/.git/**"',
        "    context:",
        '      "/docs/sessions": "Session close documents, one per work session"',
        '      "/work": "The work board: sprints, epics, tasks"',
    ]
    if patterns:
        pattern = patterns[0] if len(patterns) == 1 else "**/*.{%s}" % ",".join(
            sorted({ext for p in patterns for ext in p.replace("**/*.", "").strip("{}").split(",")}))
        lines += ["  repo-code:", "    path: /src/repo", '    pattern: "%s"' % pattern,
                  "    ignore:", '      - "**/node_modules/**"', '      - "**/dist/**"', '      - "**/vendor/**"', '      - "**/.git/**"']
    lines += ["  memory:", "    path: /src/memory", '    pattern: "**/*.md"', ""]
    p = os.path.join(root, CONFIG)
    write_text(p, "\n".join(lines))
    return {"path": CONFIG, "collections": ["repo-docs"] + (["repo-code"] if patterns else []) + ["memory"], "code_pattern": patterns}
