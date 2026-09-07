"""Can this host run the index on a GPU? The module answers yes, no, or unknown.

No GPU and no daemon are needed. Every test replaces `harness.stack.sh`, so the suite
measures the commands that the module builds and the report that it returns. `gpu.py`
runs every shell command through `stack.sh`, so one patch covers the module and the
daemon probe that it borrows from `stack`.

The two rules that matter:

- Only a container returns `yes`. `nvidia-smi` on the host proves nothing about a
  container (design law 3).
- A step that does not answer returns `unknown`, never `no` (design law 7). An
  `unknown` run never overwrites the cached answer of a run that measured something.

One test runs the real command in a subprocess against a fake `nvidia-smi` and a fake
`docker` on the PATH. It measures the text, the exit code, and the cache file.

Mutation proof (docs/MUTATION.md): M77 to M86. M85 lives in `harness/stack.py`
and M86 lives in `harness/cli.py`. The tests of this module kill both.
"""
import json
import os
import stat
import sys
import unittest
from unittest import mock

from tests.helpers import cli, make_repo, rm

from harness import gpu, stack

HOST_CARD = "GPU 0: NVIDIA GeForce RTX 3070 Ti (UUID: GPU-0a61fccd-f1a7-b6ca-84ad-b547d7bb1087)\n"
BOX_CARD = "GPU 0: NVIDIA GeForce RTX 4090 (UUID: GPU-deadbeef)\n"


def fake_sh(smi=(0, HOST_CARD), daemon=(0, "29.2.1\n"), runtimes=(0, "runc\nnvidia\n"),
            inspect=(0, "sha256:abc\n"), run=(0, BOX_CARD), calls=None):
    """Answer the five commands that the module runs. Record every call."""
    def _sh(args, cwd=None, timeout=60):
        if calls is not None:
            calls.append(list(args))
        if args[0] == "nvidia-smi":
            return smi
        if args[:2] == ["docker", "version"]:
            return daemon
        if args[:2] == ["docker", "info"]:
            return runtimes
        if args[:3] == ["docker", "image", "inspect"]:
            return inspect
        if args[:2] == ["docker", "run"]:
            return run
        return 0, ""
    return _sh


class CardNameTest(unittest.TestCase):
    def test_the_card_name_drops_the_uuid(self):
        self.assertEqual("NVIDIA GeForce RTX 3070 Ti", gpu.card_name(HOST_CARD))

    def test_no_gpu_line_is_no_card(self):
        self.assertIsNone(gpu.card_name("No devices were found\n"))
        self.assertIsNone(gpu.card_name(""))


class ProbeTest(unittest.TestCase):
    def setUp(self):
        self.root = make_repo()

    def tearDown(self):
        rm(self.root)

    def test_macos_is_no_and_names_itself_as_a_claim(self):
        calls = []
        with mock.patch.object(sys, "platform", "darwin"), \
             mock.patch.object(stack, "sh", fake_sh(calls=calls)):
            r = gpu.probe(self.root, deep=True)
        self.assertEqual("no", r["answer"])
        self.assertIn("Docker Desktop", r["reason"])
        self.assertIn("No Mac measured this yet", r["reason"])
        self.assertEqual([], calls, "the platform step runs no command")

    def test_a_host_with_no_nvidia_smi_is_no_and_names_why(self):
        with mock.patch.object(stack, "sh", fake_sh(smi=(127, "executable not found: nvidia-smi"))):
            r = gpu.probe(self.root, deep=True)
        self.assertEqual("no", r["answer"])
        self.assertIn("PATH", r["reason"])
        self.assertIn("NVIDIA driver", r["reason"])

    def test_a_driver_that_names_no_gpu_is_no(self):
        with mock.patch.object(stack, "sh", fake_sh(smi=(0, "No devices were found\n"))):
            r = gpu.probe(self.root, deep=True)
        self.assertEqual("no", r["answer"])
        self.assertIn("No devices were found", r["reason"])

    def test_a_stopped_daemon_is_unknown_and_never_no(self):
        with mock.patch.object(stack, "sh", fake_sh(daemon=(1, "Cannot connect to the Docker daemon"))):
            r = gpu.probe(self.root, deep=True)
        self.assertEqual("unknown", r["answer"])
        self.assertIn("no container can be measured", r["reason"])

    def test_a_driver_that_does_not_answer_is_unknown_and_never_no(self):
        with mock.patch.object(stack, "sh", fake_sh(smi=(124, "timeout"))):
            r = gpu.probe(self.root, deep=True)
        self.assertEqual("unknown", r["answer"])

    def test_docker_without_the_nvidia_runtime_is_no_and_names_the_fix(self):
        with mock.patch.object(stack, "sh", fake_sh(runtimes=(0, "runc\nio.containerd.runc.v2\n"))):
            r = gpu.probe(self.root, deep=True)
        self.assertEqual("no", r["answer"])
        self.assertIn("nvidia-container-toolkit", r["reason"])
        self.assertEqual(["io.containerd.runc.v2", "runc"], r["runtimes"])

    def test_a_ready_host_alone_is_unknown_and_starts_no_container(self):
        calls = []
        with mock.patch.object(stack, "sh", fake_sh(calls=calls)):
            r = gpu.probe(self.root, deep=False)
        self.assertEqual("unknown", r["answer"])
        self.assertIn("no container proved it", r["reason"])
        self.assertFalse(r["proved_by_container"])
        for c in calls:
            self.assertNotEqual(["docker", "run"], c[:2], calls)

    def test_only_a_container_returns_yes_and_it_carries_gpus_all(self):
        calls = []
        with mock.patch.object(stack, "sh", fake_sh(calls=calls)):
            r = gpu.probe(self.root, deep=True)
        self.assertEqual("yes", r["answer"])
        self.assertTrue(r["proved_by_container"])
        run = [c for c in calls if c[:2] == ["docker", "run"]]
        self.assertEqual(1, len(run), calls)
        self.assertIn("--gpus", run[0])
        self.assertIn("all", run[0])
        self.assertIn(gpu.image(self.root), run[0])

    def test_the_card_of_a_yes_comes_from_the_container_and_not_the_host(self):
        # Design law 3. The host names one card, the container names another, and the
        # report carries what the container measured.
        with mock.patch.object(stack, "sh", fake_sh()):
            r = gpu.probe(self.root, deep=True)
        self.assertEqual("NVIDIA GeForce RTX 4090", r["card"])

    def test_a_missing_image_is_unknown_and_names_the_command(self):
        with mock.patch.object(stack, "sh", fake_sh(inspect=(1, "No such image"))):
            r = gpu.probe(self.root, deep=True)
        self.assertEqual("unknown", r["answer"])
        self.assertIn("stack up", r["reason"])

    def test_a_missing_image_never_starts_a_container(self):
        # A `docker run` of an absent tag asks the registry for it. That is a network
        # call in a check that claims to measure the host.
        calls = []
        with mock.patch.object(stack, "sh", fake_sh(inspect=(1, "No such image"), calls=calls)):
            gpu.probe(self.root, deep=True)
        for c in calls:
            self.assertNotEqual(["docker", "run"], c[:2], calls)

    def test_a_container_that_cannot_reach_the_card_is_no(self):
        with mock.patch.object(stack, "sh", fake_sh(run=(125, "could not select device driver"))):
            r = gpu.probe(self.root, deep=True)
        self.assertEqual("no", r["answer"])
        self.assertIn("could not select device driver", r["reason"])

    def test_a_container_that_does_not_answer_is_unknown(self):
        with mock.patch.object(stack, "sh", fake_sh(run=(124, "timeout"))):
            r = gpu.probe(self.root, deep=True)
        self.assertEqual("unknown", r["answer"])

    def test_the_image_tag_follows_the_project_name(self):
        self.assertTrue(gpu.image(self.root).endswith("-rag:cpu"), gpu.image(self.root))
        with mock.patch.object(stack, "sh", fake_sh()):
            self.assertEqual(gpu.image(self.root), gpu.probe(self.root, deep=False)["image"])


class CacheTest(unittest.TestCase):
    def setUp(self):
        self.root = make_repo()

    def tearDown(self):
        rm(self.root)

    def test_a_measured_answer_lands_in_the_cache(self):
        with mock.patch.object(stack, "sh", fake_sh()):
            gpu.measure(self.root, deep=True)
        self.assertEqual("yes", gpu.load(self.root)["answer"])

    def test_an_unknown_run_never_overwrites_a_measured_cache(self):
        with mock.patch.object(stack, "sh", fake_sh()):
            gpu.measure(self.root, deep=True)
        with mock.patch.object(stack, "sh", fake_sh(daemon=(1, "Cannot connect to the Docker daemon"))):
            r = gpu.measure(self.root, deep=True)
        self.assertEqual("unknown", r["answer"])
        self.assertEqual("yes", gpu.load(self.root)["answer"], "a run that measured nothing erased a proof")

    def test_a_measured_no_overwrites_the_cache(self):
        with mock.patch.object(stack, "sh", fake_sh()):
            gpu.measure(self.root, deep=True)
        with mock.patch.object(stack, "sh", fake_sh(smi=(127, "executable not found: nvidia-smi"))):
            gpu.measure(self.root, deep=True)
        self.assertEqual("no", gpu.load(self.root)["answer"])

    def test_a_shallow_run_never_writes_the_cache(self):
        with mock.patch.object(stack, "sh", fake_sh()):
            gpu.measure(self.root, deep=False)
        self.assertIsNone(gpu.load(self.root))

    def test_a_damaged_cache_reads_as_no_cache(self):
        with open(gpu.path(self.root), "w", encoding="utf-8") as fh:
            fh.write("{not json")
        self.assertIsNone(gpu.load(self.root))


def fake_stack_sh(image_tag, ps_state="running", **kw):
    """`fake_sh`, plus the `docker compose` calls that `stack.status` runs.

    `gpu.note` reads the host and the running stack in one call, so one fake answers
    both. The compose branches come first: a compose command also starts with
    `docker`.
    """
    row = {"Service": "rag", "Name": "p-rag", "State": ps_state, "Health": "healthy", "Image": image_tag}
    host = fake_sh(**kw)

    def _sh(args, cwd=None, timeout=60):
        if args[-2:] == ["config", "--services"]:
            return 0, "rag\n"
        if "compose" in args and "ps" in args:
            return 0, json.dumps(row) + "\n"
        return host(args, cwd=cwd, timeout=timeout)
    return _sh


class NoteTest(unittest.TestCase):
    def setUp(self):
        self.root = make_repo()

    def tearDown(self):
        rm(self.root)

    def _cache_yes(self):
        with mock.patch.object(stack, "sh", fake_sh()):
            gpu.measure(self.root, deep=True)

    def test_the_note_names_the_command_when_the_stack_runs_the_cpu_image(self):
        self._cache_yes()
        with mock.patch.object(stack, "sh", fake_stack_sh(gpu.image(self.root))):
            note = gpu.note(self.root)
        self.assertIn("stack up --gpu", note)
        self.assertIn("rag", note)

    def test_the_note_asks_for_no_switch_when_the_stack_is_stopped(self):
        self._cache_yes()
        with mock.patch.object(stack, "sh", fake_stack_sh(gpu.image(self.root), ps_state="exited")):
            note = gpu.note(self.root)
        self.assertNotIn("stack up --gpu", note)
        self.assertIn("yes", note)

    def test_a_host_that_answers_no_prints_no_note(self):
        with mock.patch.object(stack, "sh", fake_sh(smi=(127, "executable not found: nvidia-smi"))):
            self.assertEqual("", gpu.note(self.root))

    def test_a_ready_host_with_no_cache_asks_for_the_gpu_command(self):
        with mock.patch.object(stack, "sh", fake_sh()):
            note = gpu.note(self.root)
        self.assertIn("harness gpu", note)
        self.assertIn("3070", note)


BIN_SMI = "#!/bin/sh\nprintf '%s\\n' 'GPU 0: NVIDIA GeForce RTX 3070 Ti (UUID: GPU-1)'\n"
BIN_DOCKER = """#!/bin/sh
case "$1 $2" in
  "version --format") echo 29.2.1 ;;
  "info --format") printf 'runc\\nnvidia\\n' ;;
  "image inspect") echo sha256:abc ;;
  "run --rm") printf '%s\\n' 'GPU 0: NVIDIA GeForce RTX 3070 Ti (UUID: GPU-1)' ;;
  *) exit 1 ;;
esac
"""


class GpuCliTest(unittest.TestCase):
    """The real command, in a subprocess, against a fake driver and a fake docker."""

    def setUp(self):
        self.root = make_repo()
        self.bin = os.path.join(self.root, "fakebin")
        os.makedirs(self.bin)
        for name, body in (("nvidia-smi", BIN_SMI), ("docker", BIN_DOCKER)):
            p = os.path.join(self.bin, name)
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(body)
            os.chmod(p, os.stat(p).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    def tearDown(self):
        rm(self.root)

    def _env(self):
        return {"PATH": self.bin + os.pathsep + os.environ.get("PATH", "")}

    def test_the_command_prints_yes_names_the_card_and_exits_zero(self):
        code, out, err = cli(self.root, "gpu", env=self._env())
        self.assertEqual(0, code, err)
        self.assertIn("GPU: yes", out)
        self.assertIn("RTX 3070 Ti", out)
        self.assertIn("stack up --gpu", out)
        self.assertEqual("yes", gpu.load(self.root)["answer"])

    def test_no_run_skips_the_container_and_answers_unknown(self):
        code, out, err = cli(self.root, "gpu", "--no-run", env=self._env())
        self.assertEqual(0, code, err)
        self.assertIn("GPU: unknown", out)
        self.assertIsNone(gpu.load(self.root))

    def test_init_prints_the_line_and_no_gpu_skips_it(self):
        code, out, err = cli(self.root, "init", env=self._env())
        self.assertEqual(0, code, err)
        self.assertIn("GPU: yes", out)
        code, out, err = cli(self.root, "init", "--no-gpu", env=self._env())
        self.assertEqual(0, code, err)
        self.assertNotIn("GPU:", out)

    def test_doctor_carries_the_note_of_the_last_measurement(self):
        cli(self.root, "gpu", env=self._env())
        code, out, err = cli(self.root, "doctor", env=self._env())
        self.assertEqual(0, code, err)
        self.assertIn("GPU: yes", out)


if __name__ == "__main__":
    unittest.main()
