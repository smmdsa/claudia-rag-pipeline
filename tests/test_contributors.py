"""The contributor list of README.md.

The list thanks people by name. A defect here removes a name that a person earned,
so the quiet cases are tested as hard as the loud ones. No network is needed: the
suite serves its own API answer.
"""
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
import urllib.request

from tests.helpers import PRODUCT, rm


def load_script():
    path = os.path.join(PRODUCT, "scripts", "contributors.py")
    spec = importlib.util.spec_from_file_location("contributors", path)
    mod = importlib.util.module_from_spec(spec)
    before = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.dont_write_bytecode = before
    return mod


def rows(*people):
    """One GitHub API answer. `people` holds (login, contributions, type) triples."""
    return [{"login": login, "contributions": n, "type": kind} for login, n, kind in people]


README = """# a repository

<!-- contributors:start -->
[@first](https://github.com/first)
<!-- contributors:end -->

The rest of the file.
"""


class ContributorBlockTest(unittest.TestCase):
    def setUp(self):
        self.mod = load_script()
        self.dir = tempfile.mkdtemp(prefix="contrib-")
        self.readme = os.path.join(self.dir, "README.md")
        with io.open(self.readme, "w", encoding="utf-8") as fh:
            fh.write(README)
        self.mod.README = self.readme
        os.environ["GITHUB_REPOSITORY"] = "owner/name"
        # `urlopen` is a module global of urllib. tearDown puts the real one back, so
        # a failed assertion never leaves the next test with a fake network.
        self.real_urlopen = urllib.request.urlopen

    def tearDown(self):
        urllib.request.urlopen = self.real_urlopen
        rm(self.dir)
        os.environ.pop("GITHUB_REPOSITORY", None)

    def use(self, data):
        """Answer one API call with a fixture. The real parser still runs on it."""

        class Answer:
            def read(self):
                return json.dumps(data).encode()

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        urllib.request.urlopen = lambda req, timeout=None: Answer()

    def use_no_network(self):
        def raise_url_error(req, timeout=None):
            raise urllib.error.URLError("no network")

        urllib.request.urlopen = raise_url_error

    def test_a_new_name_lands_in_the_block(self):
        self.use(rows(("first", 30, "User"), ("second", 2, "User")))
        self.assertEqual(self.mod.main([]), 0)
        text = io.open(self.readme, encoding="utf-8").read()
        self.assertIn("[@second](https://github.com/second)", text)
        self.assertIn("[@first](https://github.com/first)", text)
        self.assertIn("The rest of the file.", text)  # nothing outside the markers moved
        self.assertIn("# a repository", text)

    def test_the_order_is_most_commits_first(self):
        self.use(rows(("low", 1, "User"), ("high", 99, "User")))
        self.mod.main([])
        text = io.open(self.readme, encoding="utf-8").read()
        self.assertLess(text.index("@high"), text.index("@low"))

    def test_a_bot_never_appears(self):
        self.use(rows(("first", 30, "User"), ("copilot", 9, "Bot"),
                      ("dependabot[bot]", 5, "User")))
        self.mod.main([])
        text = io.open(self.readme, encoding="utf-8").read()
        self.assertNotIn("copilot", text)
        self.assertNotIn("dependabot", text)
        self.assertIn("@first", text)

    def test_no_answer_leaves_every_name_in_place(self):
        # An empty list is not an answer. A wrong list removes a name that a person earned.
        self.use_no_network()
        self.assertEqual(self.mod.main([]), 0)
        text = io.open(self.readme, encoding="utf-8").read()
        self.assertIn("[@first](https://github.com/first)", text)

    def test_check_reports_a_stale_list_and_writes_nothing(self):
        self.use(rows(("first", 30, "User"), ("second", 2, "User")))
        self.assertEqual(self.mod.main(["--check"]), 1)
        text = io.open(self.readme, encoding="utf-8").read()
        self.assertNotIn("@second", text)

    def test_check_is_quiet_when_the_list_is_current(self):
        self.use(rows(("first", 30, "User")))
        self.assertEqual(self.mod.main(["--check"]), 0)

    def test_a_readme_with_no_marker_is_an_error(self):
        with io.open(self.readme, "w", encoding="utf-8") as fh:
            fh.write("# no markers here\n")
        self.use(rows(("first", 30, "User")))
        with self.assertRaises(SystemExit):
            self.mod.main([])


if __name__ == "__main__":
    unittest.main()
