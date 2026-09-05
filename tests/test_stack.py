"""The Docker stacks: measure them, and start the containers that already exist.

No container and no daemon are needed. Every test replaces `harness.stack.sh`, so the
suite measures the commands that the module builds and the report that it returns.

The rule that matters: `start` never builds. A build needs the network and minutes,
and `session open` calls `start` on every session that finds a dead canary.

Mutation proof (docs/MUTATION.md): M29 to M32.
"""
import json
import os
import unittest
from unittest import mock

from tests.helpers import make_repo, rm

from harness import session, stack
from harness.util import HarnessError

PS = [
    {"Service": "rag", "Name": "p-rag", "State": "running", "Health": "healthy"},
    {"Service": "rag-agent", "Name": "p-rag-agent", "State": "exited", "Health": ""},
]


def fake_sh(ps_rows=PS, services="rag\nrag-agent\n", start_code=0, calls=None):
    """Answer the four commands that the module runs. Record every call."""
    def _sh(args, cwd=None, timeout=60):
        if calls is not None:
            calls.append(list(args))
        if args[:2] == ["docker", "version"]:
            return 0, "29.2.1\n"
        tail = args[-2:]
        if tail == ["config", "--services"]:
            return 0, services
        if "ps" in args:
            return 0, "\n".join(json.dumps(r) for r in ps_rows) + "\n"
        if args[-1] in ("start", "stop"):
            return start_code, "" if start_code == 0 else "daemon said no"
        return 0, ""
    return _sh


class StackTest(unittest.TestCase):
    def setUp(self):
        self.root = make_repo()

    def tearDown(self):
        rm(self.root)

    def test_probe_names_a_missing_docker_and_a_dead_daemon(self):
        with mock.patch.object(stack, "sh", lambda *a, **k: (127, "executable not found: docker")):
            ok, reason = stack.probe()
        self.assertFalse(ok)
        self.assertIn("PATH", reason)
        with mock.patch.object(stack, "sh", lambda *a, **k: (1, "Cannot connect to the Docker daemon")):
            ok, reason = stack.probe()
        self.assertFalse(ok)
        self.assertIn("daemon", reason)

    def test_status_splits_running_stopped_and_absent(self):
        rows = [PS[0]]  # only `rag` has a container
        with mock.patch.object(stack, "sh", fake_sh(ps_rows=rows)):
            r = stack.status(self.root, "rag")
        self.assertEqual(["rag", "rag-agent"], r["declared"])
        self.assertEqual(["rag"], r["running"])
        self.assertEqual([], r["stopped"])
        self.assertEqual(["rag-agent"], r["absent"])

    def test_start_never_builds(self):
        calls = []
        with mock.patch.object(stack, "sh", fake_sh(calls=calls)):
            stack.start(self.root, "rag")
        ran = [" ".join(c) for c in calls]
        self.assertTrue(any(c.endswith(" start") for c in ran), ran)
        for c in ran:
            self.assertNotIn("--build", c)
            self.assertNotIn(" up ", c + " ")

    def test_start_reports_what_it_started(self):
        after = [dict(PS[0]), dict(PS[1], State="running")]
        seq = [fake_sh(), fake_sh(ps_rows=after)]
        state = {"n": 0}

        def router(args, cwd=None, timeout=60):
            # The first status uses the stopped rows. The status after `start` uses the
            # running rows. `start` itself is the boundary.
            fn = seq[state["n"]]
            if args[-1] == "start":
                state["n"] = 1
            return fn(args, cwd, timeout)

        with mock.patch.object(stack, "sh", router):
            r = stack.start(self.root, "rag")
        self.assertEqual(["rag-agent"], r["started"])
        self.assertEqual("", r["note"])
        self.assertIn("started rag-agent", stack.brief_line(r))

    def test_start_refuses_to_build_a_container_that_does_not_exist(self):
        calls = []
        with mock.patch.object(stack, "sh", fake_sh(ps_rows=[], calls=calls)):
            r = stack.start(self.root, "rag")
        self.assertEqual(["rag", "rag-agent"], r["absent"])
        self.assertIn("never builds", r["note"])
        self.assertNotIn("start", [c[-1] for c in calls])

    def test_brief_line_is_empty_when_every_service_runs(self):
        rows = [dict(PS[0]), dict(PS[1], State="running")]
        with mock.patch.object(stack, "sh", fake_sh(ps_rows=rows)):
            r = stack.status(self.root, "rag")
        self.assertEqual("", stack.brief_line(r))

    def test_an_unknown_stack_name_is_an_error(self):
        with self.assertRaises(HarnessError):
            stack.status(self.root, "nosuch")

    def test_a_missing_compose_file_reports_and_never_calls_docker(self):
        os.remove(os.path.join(self.root, "infra", "rag", "docker-compose.yml"))
        calls = []
        with mock.patch.object(stack, "sh", fake_sh(calls=calls)):
            r = stack.status(self.root, "rag")
        self.assertFalse(r["docker"])
        self.assertIn("does not exist", r["reason"])
        self.assertEqual([], calls)


class SessionStackTest(unittest.TestCase):
    """`session open` uses the canary as the signal and docker as the repair."""

    def setUp(self):
        self.root = make_repo()

    def tearDown(self):
        rm(self.root)

    def _open(self, level, with_stack=True):
        health = {"level": level, "problems": ["down"], "warnings": []}
        with mock.patch.object(session.rag, "health", return_value=health), \
             mock.patch.object(session.stack, "start") as start, \
             mock.patch.object(session.time, "sleep"):
            start.return_value = {"stack": "rag", "docker": True, "reason": "", "declared": ["rag"],
                                 "services": [], "running": [], "stopped": [], "absent": [],
                                 "started": ["rag"], "note": ""}
            brief = session.open_brief(self.root, with_stack=with_stack)
        return brief, start

    def test_a_green_canary_never_calls_docker(self):
        brief, start = self._open("ok")
        start.assert_not_called()
        self.assertNotIn("stack", brief)

    def test_a_broken_canary_starts_the_stack(self):
        brief, start = self._open("broken")
        start.assert_called_once_with(self.root, "rag")
        self.assertIn("STACK: started rag", session.open_text(brief))

    def test_no_stack_never_calls_docker(self):
        brief, start = self._open("broken", with_stack=False)
        start.assert_not_called()


if __name__ == "__main__":
    unittest.main()
