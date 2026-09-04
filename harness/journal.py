"""The journal: one JSON object per line, append only.

Two kinds of line:
  {"kind":"session", "ts", "slug", "branch", "head", "commits", "dirty",
   "qa_closed":[{"id","verdict","how"}], "qa_open":[...], "surprises":[...], "failed":[...]}
  {"kind":"observation", "ts", "stock", "current", "target", "gap"}

The retro reads this file. The agent memory is not a measurement.
"""
import json
import os

from harness.util import now_iso

PATH = os.path.join(".harness", "journal.jsonl")


def path(root):
    return os.path.join(root, PATH)


def append(root, obj):
    obj = dict(obj)
    obj.setdefault("ts", now_iso())
    p = path(root)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(obj, ensure_ascii=False) + "\n")
    return obj


def read(root):
    """Return (lines, malformed). Malformed lists (line number, text)."""
    p = path(root)
    lines, bad = [], []
    if not os.path.exists(p):
        return lines, bad
    with open(p, encoding="utf-8") as fh:
        for n, raw in enumerate(fh, 1):
            if not raw.strip():
                continue
            try:
                lines.append(json.loads(raw))
            except ValueError:
                bad.append((n, raw.strip()[:80]))
    return lines, bad


def last_session(root):
    lines, _ = read(root)
    for line in reversed(lines):
        if line.get("kind") == "session":
            return line
    return None


def sessions(root):
    lines, _ = read(root)
    return [l for l in lines if l.get("kind") == "session"]


def observations(root):
    lines, _ = read(root)
    return [l for l in lines if l.get("kind") == "observation"]
