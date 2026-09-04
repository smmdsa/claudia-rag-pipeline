"""Port checks and the derived environment file.

Mutation proof (docs/MUTATION.md): M10 (every port free) turned 2 tests red.
"""
import os
import socket
import unittest

from tests.helpers import cli, make_repo, rm

from harness import env, ports


class PortsTest(unittest.TestCase):
    def test_free_and_taken(self):
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        port = s.getsockname()[1]
        try:
            os.environ["HARNESS_BOARD_PORT"] = str(port)
            rows = ports.check_ports(["HARNESS_BOARD_PORT"])
            self.assertFalse(rows[0]["free"])
            self.assertEqual(rows[0]["port"], port)
            self.assertIsNotNone(rows[0]["holder"])
            text = ports.ports_text(rows)
            self.assertIn("TAKEN", text)
            self.assertIn("HARNESS_BOARD_PORT=<port>", text)
            self.assertFalse(ports.all_free(rows))
        finally:
            s.close()
            os.environ.pop("HARNESS_BOARD_PORT", None)
        rows = ports.check_ports(["HARNESS_BOARD_PORT"])
        self.assertEqual(rows[0]["port"], 8412)

    def test_cli_exit_code_reflects_a_taken_port(self):
        root = make_repo(init=False)
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        port = s.getsockname()[1]
        try:
            code, out, _ = cli(root, "ports", env={"HARNESS_RAG_PORT": str(port)})
            self.assertEqual(code, 1)
            self.assertIn("TAKEN", out)
        finally:
            s.close()
            rm(root)

    def test_env_is_derived_and_readable(self):
        root = make_repo(init=False)
        try:
            os.environ["HARNESS_RAG_PORT"] = "9999"
            values = env.write(root)
            self.assertEqual(values["HARNESS_REPO_ROOT"], root)
            self.assertEqual(values["HARNESS_REPO_SLUG"], root.replace("/", "-"))
            self.assertTrue(values["HARNESS_MEMORY_DIR"].endswith(os.path.join("projects", root.replace("/", "-"), "memory")))
            self.assertEqual(values["HARNESS_RAG_PORT"], "9999")
            back = env.read(root)
            self.assertEqual(back["HARNESS_PROJECT"], values["HARNESS_PROJECT"])
            self.assertTrue(os.path.exists(os.path.join(root, ".harness", "env.local")))
        finally:
            os.environ.pop("HARNESS_RAG_PORT", None)
            rm(root)


if __name__ == "__main__":
    unittest.main()
