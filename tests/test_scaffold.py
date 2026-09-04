"""Upgrade, uninstall, profile, generated skills.

Mutation proof (docs/MUTATION.md): M12 (init overwrites) turned test_upgrade_rewrites_unchanged_and_keeps_edited red.
"""
import os
import unittest

from tests.helpers import cli, make_repo, rm

from harness import VERSION, manifest, profile, scaffold
from harness.util import HarnessError, read_text, write_text


class ScaffoldTest(unittest.TestCase):
    def setUp(self):
        self.root = make_repo()

    def tearDown(self):
        rm(self.root)

    def test_uninstall_dry_run_lists_owned_and_keeps_seeded(self):
        r = scaffold.uninstall(self.root, dry_run=True)
        self.assertTrue(r["dry_run"])
        self.assertIn("work/README.md", r["removed"])
        kept = dict(r["kept"])
        self.assertIn("work/ROADMAP.md", kept)
        self.assertTrue(os.path.exists(os.path.join(self.root, "work", "README.md")))

    def test_uninstall_removes_matching_owned_and_keeps_edited(self):
        p = os.path.join(self.root, "work", "templates", "task.md")
        write_text(p, read_text(p) + "\nmine\n")
        r = scaffold.uninstall(self.root, dry_run=False)
        self.assertFalse(os.path.exists(os.path.join(self.root, "work", "README.md")))
        self.assertTrue(os.path.exists(p))
        self.assertTrue(os.path.exists(os.path.join(self.root, "work", "ROADMAP.md")))
        self.assertFalse(manifest.exists(self.root))
        self.assertIn(("work/templates/task.md", "edited since install"), r["kept"])

    def test_upgrade_rewrites_unchanged_and_keeps_edited(self):
        data = manifest.load(self.root)
        data["harness_version"] = "0.0.1"
        manifest.save(self.root, data)
        readme = os.path.join(self.root, "work", "README.md")
        task = os.path.join(self.root, "work", "templates", "task.md")
        write_text(readme, "stale template content\n")
        # simulate an install of an older template: the manifest checksum matches the stale content
        scaffold.adopt(self.root, "work/README.md")
        write_text(task, read_text(task) + "\nmy edit\n")
        r = scaffold.upgrade(self.root)
        self.assertEqual((r["from"], r["to"]), ("0.0.1", VERSION))
        self.assertIn("work/README.md", r["rewritten"])
        self.assertIn("work/templates/task.md", r["edited_kept"])
        self.assertIn("The folder tree is the truth", read_text(readme))
        self.assertIn("my edit", read_text(task))
        self.assertEqual(manifest.load(self.root)["harness_version"], VERSION)

    def test_profile_set_show_and_skills(self):
        profile.set_values(self.root, [("architecture", "SPA + API"), ("languages", "TypeScript, python")])
        p = profile.show(self.root)
        self.assertEqual(p["languages"], ["typescript", "python"])
        with self.assertRaises(HarnessError):
            profile.set_values(self.root, [("colour", "blue")])
        written = profile.generate_skills(self.root)
        self.assertEqual(len(written), 3)
        text = read_text(os.path.join(self.root, ".claude", "skills", "project-map", "SKILL.md"))
        self.assertIn("SPA + API", text)
        self.assertIn("typescript, python", text)
        self.assertEqual(profile.code_patterns(p), ["**/*.{ts,tsx}", "**/*.py"])

    def test_profile_ask_reads_answers(self):
        answers = iter(["monolith", "go", "it sells", "a buyer"])
        p = profile.ask(self.root, reader=lambda q: next(answers))
        self.assertEqual(p["purpose"], "it sells")
        self.assertEqual(p["languages"], ["go"])

    def test_cli_profile_and_doctor(self):
        code, out, err = cli(self.root, "profile", "set", "purpose=sells things")
        self.assertEqual(code, 0, err)
        code, out, _ = cli(self.root, "profile", "show", "--json")
        self.assertIn("sells things", out)
        code, out, _ = cli(self.root, "doctor")
        self.assertEqual(code, 0, out)
        self.assertIn("HARNESS: sound", out)


if __name__ == "__main__":
    unittest.main()
