"""Shared helpers: repository root, shell calls, dates, output."""
import datetime as _dt
import hashlib
import json
import os
import subprocess
import sys


class HarnessError(Exception):
    """An error that the command reports to the user and exits 1."""


def sh(args, cwd=None, timeout=60):
    """Run a command. Return (exit code, stdout plus stderr).

    A missing executable returns 127. A timeout returns 124.
    """
    try:
        p = subprocess.run(args, capture_output=True, text=True, cwd=cwd, timeout=timeout)
        return p.returncode, p.stdout + p.stderr
    except FileNotFoundError:
        return 127, "executable not found: %s" % args[0]
    except subprocess.TimeoutExpired:
        return 124, "timeout after %ss: %s" % (timeout, " ".join(args))


def git_root(start=None):
    """Return the git top level of `start`, or None when git is absent."""
    code, out = sh(["git", "rev-parse", "--show-toplevel"], cwd=start or os.getcwd(), timeout=15)
    if code != 0:
        return None
    return os.path.realpath(out.strip())


def find_root(start=None):
    """Find the repository root for the commands.

    Order: `HARNESS_ROOT`, the git top level, a parent with `.harness/manifest.json`,
    the current directory.
    """
    env = os.environ.get("HARNESS_ROOT")
    if env:
        return os.path.realpath(env)
    root = git_root(start)
    if root:
        return root
    here = os.path.realpath(start or os.getcwd())
    probe = here
    while True:
        if os.path.exists(os.path.join(probe, ".harness", "manifest.json")):
            return probe
        parent = os.path.dirname(probe)
        if parent == probe:
            return here
        probe = parent


def is_git_repo(root):
    return os.path.isdir(os.path.join(root, ".git")) or git_root(root) == os.path.realpath(root)


def today():
    """Today as a date. `HARNESS_TODAY=YYYY-MM-DD` overrides it for tests."""
    forced = os.environ.get("HARNESS_TODAY")
    if forced:
        return _dt.date.fromisoformat(forced)
    return _dt.date.today()


def now():
    """Now with the local time zone. `HARNESS_NOW` overrides it for tests."""
    forced = os.environ.get("HARNESS_NOW")
    if forced:
        return parse_iso(forced)
    return _dt.datetime.now().astimezone()


def now_iso():
    return now().isoformat(timespec="seconds")


def parse_iso(text):
    """Parse an ISO 8601 timestamp. Accept a trailing `Z`."""
    text = text.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    value = _dt.datetime.fromisoformat(text)
    if value.tzinfo is None:
        value = value.astimezone()
    return value


def parse_date(text):
    """Parse `YYYY-MM-DD`. Return None on any other text."""
    if not text:
        return None
    try:
        return _dt.date.fromisoformat(str(text).strip())
    except ValueError:
        return None


def human_delta(seconds):
    """Seconds to a short label."""
    if seconds is None:
        return "not measured"
    seconds = int(seconds)
    if seconds < 3600:
        return "%d min" % (seconds // 60)
    if seconds < 86400:
        return "%d h" % (seconds // 3600)
    return "%d d" % (seconds // 86400)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_text(path):
    with open(path, encoding="utf-8", newline="") as fh:
        return fh.read()


def write_text(path, text):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def emit(data, as_json, text_fn=None):
    """Print `data` as JSON, or as the text that `text_fn` renders."""
    if as_json:
        print(json.dumps(data, indent=2, ensure_ascii=False, default=str))
    else:
        print(text_fn(data) if text_fn else data)


def eprint(*args):
    print(*args, file=sys.stderr)


def rel(root, path):
    try:
        return os.path.relpath(path, root)
    except ValueError:
        return path
