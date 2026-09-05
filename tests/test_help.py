"""The adopter's map: `help`, and the first task that `init` seeds.

Mutation proof (docs/MUTATION.md): M18 to M22.
"""
import json
import os
import unittest
from unittest import mock

from tests.helpers import cli, make_repo, rm

from harness import board, help as help_, manifest, scaffold
from harness.util import read_text, write_text


class HelpTest(unittest.TestCase):
    def setUp(self):
        self.root = make_repo()

    def tearDown(self):
        rm(self.root)

    def test_overview_names_the_rules_files_and_the_topics(self):
        code, out, err = cli(self.root, "help")
        self.assertEqual(0, code, err)
        self.assertIn("WHAT YOU OWN", out)
        self.assertIn("CLAUDE.md", out)
        self.assertIn("work/README.md", out)
        self.assertIn("docs/DESIGN-LAWS.md", out)
        for topic in help_.TOPICS:
            self.assertIn(topic, out)

    def test_overview_names_no_path_that_init_does_not_create(self):
        """`help` offers `init` as the fix for a missing path. A path that `init` never
        creates turns that offer into a false instruction. Law 3: a path that still
        exists does not prove that the path is correct. This repository holds
        docs/DESIGN-LAWS.md, so only a fresh repository measures this."""
        text = help_.help_text(help_.report(self.root))
        self.assertNotIn("MISSING", text)

    def test_unknown_topic_exits_1_and_names_every_topic(self):
        code, out, err = cli(self.root, "help", "nosuch")
        self.assertEqual(1, code)
        for topic in help_.TOPICS:
            self.assertIn(topic, err)

    def test_skills_are_read_from_the_tree_not_from_a_list(self):
        write_text(os.path.join(self.root, ".claude", "skills", "zz-made-up", "SKILL.md"),
                   "---\nname: zz-made-up\ndescription: A skill that no template holds. Use it never.\n---\n\nbody\n")
        code, out, err = cli(self.root, "help", "skills")
        self.assertEqual(0, code, err)
        self.assertIn("zz-made-up", out)
        self.assertIn("A skill that no template holds.", out)
        self.assertIn("session-start", out)

    def test_skills_reports_the_count_it_found(self):
        rows = help_.skills(self.root)
        code, out, _ = cli(self.root, "help", "skills")
        self.assertEqual(0, code)
        self.assertIn("INSTALLED SKILLS (%d)" % len(rows), out)
        self.assertTrue(rows)

    def test_eye_topic_follows_harness_board_eye(self):
        """A hard-coded copy of the eye values passes a plain `assertIn`. Patch the
        source of truth instead: the topic must print the value that the code declares
        now, not the value that the author typed once."""
        with mock.patch.object(board, "EYE", ("NONE", "GLANCE", "RUN", "ZZPROBE")):
            text = help_.help_text(help_.report(self.root, "eye"))
        self.assertIn("ZZPROBE", text)

    def test_board_topic_follows_harness_board_states(self):
        with mock.patch.object(board, "STATES", ("todo", "in-progress", "done", "zzprobe")):
            text = help_.help_text(help_.report(self.root, "board"))
        self.assertIn("zzprobe", text)

    def test_eye_topic_names_the_flag_that_closes_an_eye_task(self):
        code, out, err = cli(self.root, "help", "eye")
        self.assertEqual(0, code, err)
        self.assertIn("--verdict", out)

    def test_help_runs_before_init_and_marks_the_missing_paths(self):
        bare = make_repo(init=False)
        try:
            code, out, err = cli(bare, "help")
            self.assertEqual(0, code, err)
            self.assertIn("MISSING", out)
        finally:
            rm(bare)

    def test_json_carries_the_sections(self):
        code, out, _ = cli(self.root, "help", "--json")
        self.assertEqual(0, code)
        data = json.loads(out)
        self.assertEqual("overview", data["topic"])
        self.assertTrue(data["sections"])
        self.assertEqual(list(help_.TOPICS), data["topics"])


class SeedTaskTest(unittest.TestCase):
    def setUp(self):
        self.root = make_repo(seed_task=True)
        self.seed = os.path.join(self.root, *scaffold.SEED_TASK.split("/"))

    def tearDown(self):
        rm(self.root)

    def test_init_writes_the_first_task_and_the_manifest_ignores_it(self):
        self.assertTrue(os.path.exists(self.seed))
        data = manifest.load(self.root)
        self.assertNotIn(scaffold.SEED_TASK, data["files"])

    def test_doctor_stays_sound_after_the_first_task_moves(self):
        tree = board.scan(self.root)
        sp = board.new_sprint(self.root, tree, "S", "2026-09-01", "2026-09-14")
        tree = board.scan(self.root)
        ep = board.new_epic(self.root, tree, sp["id"], "E")
        tree = board.scan(self.root)
        board.assign(self.root, tree, "TASK-0001", ep["id"])
        for to in ("in-progress", "done"):
            tree = board.scan(self.root)
            board.move(self.root, tree, "TASK-0001", to)
        self.assertFalse(os.path.exists(self.seed))
        self.assertEqual("sound", manifest.doctor(self.root)["state"])

    def test_init_never_writes_the_first_task_twice(self):
        os.remove(self.seed)
        write_text(os.path.join(self.root, "work", "backlog", "TASK-0009-mine.md"),
                   "---\nid: TASK-0009\ntitle: Mine\nwork: S\neye: NONE\n---\n\n# TASK-0009 — Mine\n")
        scaffold.init(self.root)
        self.assertFalse(os.path.exists(self.seed))

    def test_init_text_points_at_help(self):
        code, out, err = cli(self.root, "init")
        self.assertEqual(0, code, err)
        self.assertIn("harness help", out)




class ReseedTest(unittest.TestCase):
    """A repository can keep its own board out of git. A clone then lacks every seeded
    file. `session open` writes them again, and it never touches a real defect.

    Mutation proof (docs/MUTATION.md): M25, M26.
    """

    def setUp(self):
        self.root = make_repo()

    def tearDown(self):
        rm(self.root)

    def _drop_seeded(self):
        for rel in ("docs/ACTIVITY.md", ".harness/targets.json", "work/ROADMAP.md"):
            os.remove(os.path.join(self.root, *rel.split("/")))

    def test_doctor_marks_a_missing_seeded_file(self):
        self._drop_seeded()
        report = manifest.doctor(self.root)
        self.assertEqual("damaged", report["state"])
        self.assertTrue(manifest.only_missing_seeded(report))
        self.assertEqual({"missing-seeded"}, {p.get("kind") for p in report["problems"]})

    def test_a_damaged_owned_file_is_never_only_missing_seeded(self):
        self._drop_seeded()
        write_text(os.path.join(self.root, "work", "README.md"), "the adopter edited this\n")
        report = manifest.doctor(self.root)
        self.assertFalse(manifest.only_missing_seeded(report))

    def test_session_open_writes_the_missing_seeded_files_again(self):
        from harness import session
        self._drop_seeded()
        brief = session.open_brief(self.root, with_rag=False)
        self.assertIn("reseeded", brief)
        self.assertEqual("sound", brief["doctor"]["state"])
        self.assertIn("RESEED", session.open_text(brief))
        for rel in ("docs/ACTIVITY.md", ".harness/targets.json", "work/ROADMAP.md"):
            self.assertTrue(os.path.exists(os.path.join(self.root, *rel.split("/"))))

    def test_session_open_never_hides_a_damaged_owned_file(self):
        from harness import session
        write_text(os.path.join(self.root, "work", "README.md"), "the adopter edited this\n")
        brief = session.open_brief(self.root, with_rag=False)
        self.assertNotIn("reseeded", brief)
        self.assertEqual("damaged", brief["doctor"]["state"])

    def test_reseed_leaves_a_compact_settings_file_alone(self):
        """`json.dumps` expands a compact array. An unconditional write reports a diff
        that nobody made, and a clone shows a dirty tree on its first command."""
        from harness import session
        p = os.path.join(self.root, ".claude", "settings.json")
        text = read_text(p).replace('"enabledMcpjsonServers": [\n    "qmd"\n  ]',
                                    '"enabledMcpjsonServers": ["qmd"]')
        write_text(p, text)
        self._drop_seeded()
        session.open_brief(self.root, with_rag=False)
        self.assertEqual(text, read_text(p))

    def test_reseed_leaves_the_manifest_alone(self):
        from harness import session
        before = read_text(os.path.join(self.root, ".harness", "manifest.json"))
        self._drop_seeded()
        session.open_brief(self.root, with_rag=False)
        after = read_text(os.path.join(self.root, ".harness", "manifest.json"))
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
