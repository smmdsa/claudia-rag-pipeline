"""Front matter reader and writer.

Mutation proof (docs/MUTATION.md): M13 dropped the list items and turned 5 tests red, 2 of them here.
"""
import unittest

from tests.helpers import PRODUCT  # noqa: F401  (adds the product to sys.path)

from harness import frontmatter as fm


class FrontMatterTest(unittest.TestCase):
    def test_parse_scalars_lists_and_body(self):
        text = "---\nid: TASK-0001\ntitle: \"A: title\"\nblocked-by:\n  - TASK-0002\n  - TASK-0003\nrefs: [a.py, b.py]\nempty:\n---\n\n# Body\n"
        fields, body = fm.parse(text)
        self.assertEqual(fields["id"], "TASK-0001")
        self.assertEqual(fields["title"], "A: title")
        self.assertEqual(fields["blocked-by"], ["TASK-0002", "TASK-0003"])
        self.assertEqual(fields["refs"], ["a.py", "b.py"])
        self.assertEqual(fields["empty"], "")
        self.assertEqual(body.strip(), "# Body")

    def test_no_front_matter(self):
        fields, body = fm.parse("# just a body\n")
        self.assertEqual(fields, {})
        self.assertEqual(body, "# just a body\n")

    def test_dump_round_trip(self):
        fields = {"id": "TASK-0009", "title": "Fix: the thing", "blocked-by": ["TASK-0001"], "refs": [], "due": "2026-09-30"}
        text = fm.dump(fields, "# T\n")
        back, body = fm.parse(text)
        self.assertEqual(back["id"], "TASK-0009")
        self.assertEqual(back["title"], "Fix: the thing")
        self.assertEqual(back["blocked-by"], ["TASK-0001"])
        self.assertEqual(back["refs"], [])
        self.assertEqual(back["due"], "2026-09-30")
        self.assertIn("# T", body)

    def test_inline_comment_is_dropped(self):
        fields, _ = fm.parse("---\nwork: S   # my cost\n---\n")
        self.assertEqual(fields["work"], "S")

    def test_crlf(self):
        fields, body = fm.parse("---\r\nid: X\r\n---\r\nbody")
        self.assertEqual(fields["id"], "X")
        self.assertEqual(body, "body")


if __name__ == "__main__":
    unittest.main()
