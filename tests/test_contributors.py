"""The contributor list of README.md.

The list thanks people by name and picture. A defect here removes a name that a
person earned, so the quiet cases are tested as hard as the loud ones. No network is
needed: the suite serves its own API answers.

The script reads two endpoints, so the fake answers by url. A fake that answers the
same body to both hides which endpoint a name came from, and these tests need that
difference: `/contributors` is a cached aggregate, and `/commits` is the fresh page.
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


def avatar(login):
    return "https://avatars.githubusercontent.com/%s?v=4" % login


def rows(*people):
    """The `/contributors` answer. `people` holds (login, contributions, type) triples."""
    return [{"login": login, "contributions": n, "type": kind, "avatar_url": avatar(login)}
            for login, n, kind in people]


def commits(*people):
    """The `/commits` answer. `people` holds (login, type) pairs, one entry per commit."""
    return [{"author": {"login": login, "type": kind, "avatar_url": avatar(login)}}
            for login, kind in people]


README = """# a repository

<!-- contributors:start -->
<table>
  <tr><td align="center"><a href="https://github.com/first"><img src="%s&s=96" width="96" alt=""><br><sub><b>first</b></sub></a></td></tr>
</table>
<!-- contributors:end -->

The rest of the file.
""" % avatar("first")


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

    def use(self, contributors_rows, commits_rows=None):
        """Answer both endpoints with fixtures. The real parser still runs on them."""
        commits_rows = [] if commits_rows is None else commits_rows

        class Answer:
            def __init__(self, data):
                self.data = data

            def read(self):
                return json.dumps(self.data).encode()

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        def fake(req, timeout=None):
            url = req.full_url if hasattr(req, "full_url") else str(req)
            return Answer(commits_rows if "/commits" in url else contributors_rows)

        urllib.request.urlopen = fake

    def use_no_network(self):
        def raise_url_error(req, timeout=None):
            raise urllib.error.URLError("no network")

        urllib.request.urlopen = raise_url_error

    def text(self):
        return io.open(self.readme, encoding="utf-8").read()

    def test_a_new_name_lands_in_the_block(self):
        self.use(rows(("first", 30, "User"), ("second", 2, "User")))
        self.assertEqual(self.mod.main([]), 0)
        text = self.text()
        self.assertIn("<b>second</b>", text)
        self.assertIn('href="https://github.com/second"', text)
        self.assertIn("<b>first</b>", text)
        self.assertIn("The rest of the file.", text)  # nothing outside the markers moved
        self.assertIn("# a repository", text)

    def test_a_picture_carries_every_name(self):
        self.use(rows(("first", 30, "User"), ("second", 2, "User")))
        self.mod.main([])
        text = self.text()
        self.assertEqual(text.count("<img src="), 2)
        self.assertIn('width="96"', text)
        self.assertIn("s=96", text)  # the API url takes the size as a query parameter

    def test_a_name_the_cached_aggregate_missed_still_lands(self):
        """THE regression of 2026-09-06.

        `/contributors` is a cached aggregate. It named 1 person while the repository
        page named 3, and a contributor who landed 40 minutes earlier was missing.
        `/commits` is fresh. A name from either endpoint counts.
        """
        self.use(rows(("first", 30, "User")), commits(("newcomer", "User")))
        self.assertEqual(self.mod.main([]), 0)
        text = self.text()
        self.assertIn("<b>newcomer</b>", text)
        self.assertIn("<b>first</b>", text)

    def test_the_aggregate_ranks_first_and_the_fresh_name_follows(self):
        self.use(rows(("low", 1, "User"), ("high", 99, "User")), commits(("newcomer", "User")))
        self.mod.main([])
        text = self.text()
        self.assertLess(text.index("<b>high</b>"), text.index("<b>low</b>"))
        self.assertLess(text.index("<b>low</b>"), text.index("<b>newcomer</b>"))

    def test_a_name_in_both_endpoints_appears_once(self):
        self.use(rows(("first", 30, "User")), commits(("first", "User"), ("first", "User")))
        self.mod.main([])
        self.assertEqual(self.text().count("<b>first</b>"), 1)

    def test_a_bot_never_appears(self):
        self.use(rows(("first", 30, "User"), ("copilot", 9, "Bot"),
                      ("dependabot[bot]", 5, "User")),
                 commits(("renovate", "Bot")))
        self.mod.main([])
        text = self.text()
        self.assertNotIn("copilot", text)
        self.assertNotIn("dependabot", text)
        self.assertNotIn("renovate", text)
        self.assertIn("<b>first</b>", text)

    def test_a_commit_with_no_resolved_account_is_skipped(self):
        # GitHub answers `author: null` when it cannot map the address to an account.
        self.use(rows(("first", 30, "User")), [{"author": None}])
        self.assertEqual(self.mod.main([]), 0)
        self.assertIn("<b>first</b>", self.text())

    def test_no_answer_leaves_every_name_in_place(self):
        # An empty list is not an answer. A wrong list removes a name that a person earned.
        self.use_no_network()
        self.assertEqual(self.mod.main([]), 0)
        self.assertIn("<b>first</b>", self.text())

    def test_an_empty_list_leaves_every_name_in_place(self):
        # The regression that Copilot found on PR 7. Both endpoints answer with an
        # empty array while GitHub counts a repository, and every earned name would go.
        self.use([], [])
        self.assertEqual(self.mod.main([]), 0)
        self.assertIn("<b>first</b>", self.text())

    def test_an_answer_of_only_bots_leaves_every_name_in_place(self):
        self.use(rows(("copilot", 9, "Bot"), ("dependabot[bot]", 5, "User")))
        self.assertEqual(self.mod.main([]), 0)
        text = self.text()
        self.assertIn("<b>first</b>", text)
        self.assertNotIn("copilot", text)

    def test_an_empty_list_never_reports_a_stale_file(self):
        self.use([], [])
        self.assertEqual(self.mod.main(["--check"]), 0)

    def test_a_message_names_the_api_url_and_not_the_slug(self):
        self.use_no_network()
        out = io.StringIO()
        real = sys.stdout
        sys.stdout = out
        try:
            self.mod.main([])
        finally:
            sys.stdout = real
        printed = out.getvalue()
        self.assertIn("https://api.github.com/repos/owner/name/contributors", printed)
        self.assertIn("https://api.github.com/repos/owner/name/commits", printed)

    def test_check_reports_a_stale_list_and_writes_nothing(self):
        self.use(rows(("first", 30, "User"), ("second", 2, "User")))
        self.assertEqual(self.mod.main(["--check"]), 1)
        self.assertNotIn("second", self.text())

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
