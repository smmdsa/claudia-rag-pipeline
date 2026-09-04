"""Shared helpers for the tests. Each test gets a fresh git repository in a temp dir."""
import os
import shutil
import subprocess
import sys
import tempfile

PRODUCT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PRODUCT not in sys.path:
    sys.path.insert(0, PRODUCT)

from harness import board, scaffold  # noqa: E402


def git(root, *args):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"] + list(args),
                          cwd=root, capture_output=True, text=True)


def make_repo(init=True):
    root = os.path.realpath(tempfile.mkdtemp(prefix="hrp-"))
    git(root, "init", "-q", "-b", "main")
    if init:
        scaffold.init(root)
    return root


def commit_all(root, msg="c"):
    git(root, "add", "-A")
    return git(root, "commit", "-q", "-m", msg)


def seed_board(root, starts="2026-09-01", ends="2026-09-14"):
    """One sprint, one epic, three tasks. Return the ids."""
    tree = board.scan(root)
    sp = board.new_sprint(root, tree, "Sprint one", starts, ends, goal="ship")
    tree = board.scan(root)
    ep = board.new_epic(root, tree, sp["id"], "Epic one")
    tree = board.scan(root)
    t1 = board.new_task(root, tree, "First task", epic=ep["id"], work="S", eye="NONE")
    tree = board.scan(root)
    t2 = board.new_task(root, tree, "Second task", epic=ep["id"], work="M", eye="RUN")
    tree = board.scan(root)
    t3 = board.new_task(root, tree, "Third task", epic=ep["id"], work="S", eye="GLANCE", blocked_by=[t1["id"]])
    return {"sprint": sp["id"], "epic": ep["id"], "t1": t1["id"], "t2": t2["id"], "t3": t3["id"]}


def cli(root, *args, env=None, stdin=None):
    """Run the real entry point in a subprocess. Return (code, stdout, stderr)."""
    e = dict(os.environ, PYTHONPATH=PRODUCT, HARNESS_ROOT=root)
    e.pop("HARNESS_TODAY", None)
    e.update(env or {})
    p = subprocess.run([sys.executable, "-m", "harness"] + list(args), cwd=root, capture_output=True,
                       text=True, env=e, input=stdin, timeout=120)
    return p.returncode, p.stdout, p.stderr


def rm(root):
    shutil.rmtree(root, ignore_errors=True)
