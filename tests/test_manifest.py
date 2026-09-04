"""The manifest and the integrity gate: init, doctor, adopt, restore.

Mutation proof: see docs/MUTATION.md.
"""
import json
import os
import unittest

from tests.helpers import cli, make_repo, rm

from harness import VERSION, manifest, scaffold
from harness.util import read_text, write_text


class ManifestTest(unittest.TestCase):
    def setUp(self):
        self.root = make_repo(init=False)

    def tearDown(self):
        rm(self.root)

    def test_not_initialised_is_exit_2(self):
        r = manifest.doctor(self.root)
        self.assertEqual((r["state"], r["exit"]), ("not-initialised", 2))
        code, out, _ = cli(self.root, "doctor")
        self.assertEqual(code, 2)
        self.assertIn("harness init", out)

    def test_init_is_idempotent(self):
        first = scaffold.init(self.root)
        self.assertGreater(len(first["created"]), 20)
        second = scaffold.init(self.root)
        self.assertEqual(second["created"], [])
        # the first run also created one .gitkeep per KEEP_DIRS entry; the second run keeps every file
        self.assertEqual(len(second["kept"]), len(first["created"]) - len(scaffold.KEEP_DIRS))
        data = manifest.load(self.root)
        self.assertEqual(data["harness_version"], VERSION)
        self.assertIn("CLAUDE.md", data["files"])
        self.assertEqual(data["files"]["work/README.md"]["kind"], "owned")
        self.assertEqual(data["files"]["work/ROADMAP.md"]["kind"], "seeded")

    def test_sound_after_init(self):
        scaffold.init(self.root)
        r = manifest.doctor(self.root)
        self.assertEqual((r["state"], r["exit"]), ("sound", 0), r["problems"])
        self.assertTrue(any("profile" in n for n in r["notes"]))

    def test_edited_owned_file_is_damaged_and_names_the_fix(self):
        scaffold.init(self.root)
        p = os.path.join(self.root, "work", "README.md")
        write_text(p, read_text(p) + "\nan edit\n")
        r = manifest.doctor(self.root)
        self.assertEqual(r["exit"], 1)
        what = [x["what"] for x in r["problems"]]
        self.assertTrue(any("work/README.md differs" in w for w in what), what)
        self.assertTrue(any("restore work/README.md" in x["fix"] for x in r["problems"]))

    def test_missing_file_is_damaged(self):
        scaffold.init(self.root)
        os.remove(os.path.join(self.root, "work", "templates", "task.md"))
        r = manifest.doctor(self.root)
        self.assertEqual(r["exit"], 1)
        self.assertTrue(any("work/templates/task.md is missing" in x["what"] for x in r["problems"]))

    def test_hooks_removed_is_damaged(self):
        scaffold.init(self.root)
        p = os.path.join(self.root, ".claude", "settings.json")
        data = json.loads(read_text(p))
        del data["hooks"]["Stop"]
        write_text(p, json.dumps(data))
        r = manifest.doctor(self.root)
        self.assertEqual(r["exit"], 1)
        self.assertTrue(any("Stop" in x["what"] and "hooks install" in x["fix"] for x in r["problems"]), r["problems"])
        scaffold.install_hooks(self.root)
        self.assertEqual(manifest.doctor(self.root)["exit"], 0)

    def test_malformed_journal_line_is_damaged(self):
        scaffold.init(self.root)
        with open(os.path.join(self.root, ".harness", "journal.jsonl"), "a", encoding="utf-8") as fh:
            fh.write('{"kind": "session"}\nnot json\n')
        r = manifest.doctor(self.root)
        self.assertEqual(r["exit"], 1)
        self.assertTrue(any("line 2 is not JSON" in x["what"] for x in r["problems"]), r["problems"])

    def test_version_mismatch_is_damaged(self):
        scaffold.init(self.root)
        data = manifest.load(self.root)
        data["harness_version"] = "0.0.1"
        manifest.save(self.root, data)
        r = manifest.doctor(self.root)
        self.assertEqual(r["exit"], 1)
        self.assertTrue(any("0.0.1" in x["what"] and "upgrade" in x["fix"] for x in r["problems"]))

    def test_adopt_and_restore(self):
        scaffold.init(self.root)
        p = os.path.join(self.root, "work", "README.md")
        write_text(p, read_text(p) + "\nlocal rule\n")
        self.assertEqual(manifest.doctor(self.root)["exit"], 1)
        scaffold.adopt(self.root, "work/README.md")
        self.assertEqual(manifest.doctor(self.root)["exit"], 0)
        r = scaffold.restore(self.root, "work/README.md")
        self.assertIn("-local rule", r["diff"])
        self.assertNotIn("local rule", read_text(p))
        self.assertEqual(manifest.doctor(self.root)["exit"], 0)

    def test_existing_claude_md_sends_rules_to_rules_dir(self):
        write_text(os.path.join(self.root, "CLAUDE.md"), "# mine\n")
        r = scaffold.init(self.root)
        self.assertEqual(r["rules_path"], ".claude/rules/harness.md")
        self.assertTrue(os.path.exists(os.path.join(self.root, ".claude", "rules", "harness.md")))
        self.assertEqual(read_text(os.path.join(self.root, "CLAUDE.md")), "# mine\n")
        self.assertIn("Glossary", read_text(os.path.join(self.root, ".claude", "rules", "harness.md")))

    def test_existing_settings_keeps_keys_and_gets_hooks(self):
        write_text(os.path.join(self.root, ".claude", "settings.json"), json.dumps({"permissions": {"allow": ["Bash(make:*)"]}, "model": "opus"}))
        scaffold.init(self.root)
        data = json.loads(read_text(os.path.join(self.root, ".claude", "settings.json")))
        self.assertEqual(data["model"], "opus")
        self.assertIn("Bash(make:*)", data["permissions"]["allow"])
        self.assertIn("Bash(npm:*)", data["permissions"]["deny"])
        self.assertIn("SessionStart", data["hooks"])
        self.assertEqual(manifest.doctor(self.root)["exit"], 0)

    def test_gitignore_lines_are_added_once(self):
        write_text(os.path.join(self.root, ".gitignore"), "node_modules/\n")
        scaffold.init(self.root)
        scaffold.init(self.root)
        text = read_text(os.path.join(self.root, ".gitignore"))
        self.assertEqual(text.count(".harness/env.local"), 1)
        self.assertTrue(text.startswith("node_modules/"))

    def test_project_name_is_rendered(self):
        scaffold.init(self.root)
        self.assertIn(os.path.basename(self.root), read_text(os.path.join(self.root, "CLAUDE.md")))
        self.assertNotIn("{{PROJECT}}", read_text(os.path.join(self.root, "docs", "ACTIVITY.md")))


if __name__ == "__main__":
    unittest.main()
