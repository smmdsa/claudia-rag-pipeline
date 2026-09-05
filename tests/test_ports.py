"""Port checks and the derived environment file.

Mutation proof (docs/MUTATION.md): M10 (every port free) turned 2 tests red;
M44 (port_for ignores the env file) 2 red.
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

    def test_port_for_reads_the_env_file_that_docker_compose_reads(self):
        """`docker compose --env-file` reads this file. The checker must read it too."""
        root = make_repo(init=False)
        try:
            os.environ["HARNESS_RAG_PORT"] = "9410"
            env.write(root)
            os.environ.pop("HARNESS_RAG_PORT")
            self.assertEqual(ports.port_for("HARNESS_RAG_PORT", root), 9410)
        finally:
            os.environ.pop("HARNESS_RAG_PORT", None)
            rm(root)

    def test_the_shell_wins_over_the_env_file(self):
        root = make_repo(init=False)
        try:
            os.environ["HARNESS_RAG_PORT"] = "9410"
            env.write(root)
            os.environ["HARNESS_RAG_PORT"] = "9510"
            self.assertEqual(ports.port_for("HARNESS_RAG_PORT", root), 9510)
        finally:
            os.environ.pop("HARNESS_RAG_PORT", None)
            rm(root)

    def test_no_env_file_falls_to_the_default(self):
        root = make_repo(init=False)
        try:
            os.environ.pop("HARNESS_RAG_PORT", None)
            self.assertEqual(ports.port_for("HARNESS_RAG_PORT", root), 8410)
        finally:
            rm(root)

    def test_stack_ports_check_the_port_that_docker_publishes(self):
        from harness import stack
        root = make_repo(init=False)
        try:
            os.environ["HARNESS_BOARD_PORT"] = "9412"
            env.write(root)
            os.environ.pop("HARNESS_BOARD_PORT")
            declared = {v: k for k, v in env.read(root).items()}
            self.assertEqual(declared["9412"], "HARNESS_BOARD_PORT")
            self.assertEqual(ports.port_for("HARNESS_BOARD_PORT", root), 9412)
            self.assertIn("HARNESS_BOARD_PORT", stack.STACK_PORTS["board"])
        finally:
            os.environ.pop("HARNESS_BOARD_PORT", None)
            rm(root)


if __name__ == "__main__":
    unittest.main()
