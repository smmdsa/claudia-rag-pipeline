"""The policies of the product, measured on the files.

- No module of the harness imports a third-party package (law: standard library only).
- No executable file contains the WSL wrapper string that design law 6 forbids.
- No rendered template keeps a `{{...}}` placeholder, except the task molds.

Mutation proof: see docs/MUTATION.md.
"""
import ast
import os
import re
import sys
import unittest

from tests.helpers import PRODUCT, make_repo, rm

HARNESS = os.path.join(PRODUCT, "harness")
EXECUTABLE = (".py", ".sh", ".js", ".mjs", ".json", ".yml", ".yaml")
FORBIDDEN = "ws" + "l "  # split so this file itself does not carry the literal


def walk(base, exts=None):
    for dirpath, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git")]
        for f in files:
            if exts is None or f.endswith(exts) or f == "Dockerfile" or f == "SKILL.md":
                yield os.path.join(dirpath, f)


class PolicyTest(unittest.TestCase):
    def test_standard_library_only(self):
        stdlib = set(sys.stdlib_module_names)
        offenders = []
        files = [p for p in walk(HARNESS, (".py",)) if p.endswith(".py")]
        self.assertGreater(len(files), 15)
        for path in files:
            with open(path, encoding="utf-8") as fh:
                tree = ast.parse(fh.read(), path)
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [a.name.split(".")[0] for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    names = [node.module.split(".")[0]]
                for n in names:
                    if n not in stdlib and n not in ("harness", "tests"):
                        offenders.append("%s imports %s" % (os.path.relpath(path, PRODUCT), n))
        self.assertEqual(offenders, [])

    def test_no_wsl_wrapper_in_executables(self):
        hits = []
        for base in (HARNESS, os.path.join(PRODUCT, "tests")):
            for path in walk(base, EXECUTABLE):
                with open(path, encoding="utf-8", errors="replace") as fh:
                    if FORBIDDEN in fh.read():
                        hits.append(os.path.relpath(path, PRODUCT))
        self.assertEqual(hits, [])

    def test_rendered_templates_have_no_placeholders(self):
        root = make_repo()
        try:
            left = []
            for path in walk(root):
                rel = os.path.relpath(path, root)
                if rel.startswith("work/templates/") or rel.startswith(".git"):
                    continue
                with open(path, encoding="utf-8", errors="replace") as fh:
                    if re.search(r"\{\{[A-Z_]+\}\}", fh.read()):
                        left.append(rel)
            self.assertEqual(left, [])
        finally:
            rm(root)

    def test_python_version_floor_is_declared(self):
        from harness import MIN_PYTHON
        self.assertEqual(MIN_PYTHON, (3, 10))
        self.assertGreaterEqual(sys.version_info[:2], MIN_PYTHON)


if __name__ == "__main__":
    unittest.main()
