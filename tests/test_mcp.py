"""The link between the agent and the index.

Mutation proof (docs/MUTATION.md): M41 (a later index still reads as live) 1 red,
M42 (the elapsed time is read as an absolute time) 1 red.
"""
import unittest

from harness import mcp


class ElapsedTest(unittest.TestCase):
    def test_reads_every_posix_shape(self):
        self.assertEqual(mcp.elapsed_seconds("00:42"), 42)
        self.assertEqual(mcp.elapsed_seconds("03:04"), 184)
        self.assertEqual(mcp.elapsed_seconds("01:02:03"), 3723)
        self.assertEqual(mcp.elapsed_seconds("2-01:02:03"), 176523)

    def test_rejects_what_it_cannot_read(self):
        for bad in ("", None, "later", "1:2:3:4", "Sat Sep  5 13:48:04 2026"):
            self.assertIsNone(mcp.elapsed_seconds(bad))


class Rfc3339Test(unittest.TestCase):
    def test_reads_the_nine_digits_that_docker_prints(self):
        a = mcp.parse_rfc3339("2026-09-05T19:51:11.013510340Z")
        b = mcp.parse_rfc3339("2026-09-05T19:51:11.013510Z")
        self.assertIsNotNone(a)
        self.assertAlmostEqual(a, b, places=3)

    def test_reads_an_offset_with_no_colon(self):
        self.assertEqual(mcp.parse_rfc3339("2026-09-05T16:51:11.0Z"),
                         mcp.parse_rfc3339("2026-09-05T13:51:11.0-0300"))

    def test_a_container_that_never_ran_is_not_a_time(self):
        self.assertIsNone(mcp.parse_rfc3339("0001-01-01T00:00:00Z"))

    def test_rejects_what_it_cannot_read(self):
        for bad in ("", None, "2026-09-05", "yesterday"):
            self.assertIsNone(mcp.parse_rfc3339(bad))


class AncestorTest(unittest.TestCase):
    def walk(self, chain, pid=100, now=1000.0):
        real = mcp.proc
        mcp.proc = lambda p: chain.get(p)
        try:
            return mcp.agent_started_at(pid=pid, now=now)
        finally:
            mcp.proc = real

    def test_finds_the_client_above_the_shell(self):
        chain = {100: (50, 30.0, "python3"), 50: (10, 120.0, "bash"), 10: (1, 900.0, "claude")}
        self.assertEqual(self.walk(chain), 100.0)

    def test_a_command_outside_the_client_measures_nothing(self):
        chain = {100: (50, 30.0, "python3"), 50: (1, 120.0, "bash")}
        self.assertIsNone(self.walk(chain))

    def test_a_loop_in_the_chain_stops(self):
        chain = {100: (50, 30.0, "python3"), 50: (100, 120.0, "bash")}
        self.assertIsNone(self.walk(chain))

    def test_an_unreadable_process_measures_nothing(self):
        self.assertIsNone(self.walk({100: None}))


class LinkTest(unittest.TestCase):
    def state(self, agent, index):
        return mcp.link_state("/nowhere", agent=agent, index=index)

    def test_an_index_that_started_later_is_stale(self):
        r = self.state(agent=1000.0, index=1600.0)
        self.assertEqual(r["state"], "stale")
        self.assertEqual(r["gap"], 600.0)
        self.assertIn("restart", mcp.link_line(r).lower())

    def test_an_index_that_started_first_is_live(self):
        r = self.state(agent=1600.0, index=1000.0)
        self.assertEqual(r["state"], "live")
        self.assertEqual(mcp.link_line(r), "")

    def test_no_client_measures_nothing_and_never_reads_docker(self):
        """A command outside Claude Code costs no docker call at all."""
        calls = []
        real_index, real_agent = mcp.index_started_at, mcp.agent_started_at
        mcp.index_started_at = lambda *a, **k: calls.append(1)
        mcp.agent_started_at = lambda *a, **k: None
        try:
            r = mcp.link_state("/nowhere")
        finally:
            mcp.index_started_at, mcp.agent_started_at = real_index, real_agent
        self.assertEqual(r["state"], "unknown")
        self.assertEqual(calls, [])
        self.assertEqual(mcp.link_line(r), "")

    def test_no_container_time_measures_nothing(self):
        r = self.state(agent=1000.0, index=None)
        self.assertEqual(r["state"], "unknown")
        self.assertIn("not measured", mcp.link_text(r))
        self.assertEqual(mcp.link_line(r), "")


if __name__ == "__main__":
    unittest.main()
