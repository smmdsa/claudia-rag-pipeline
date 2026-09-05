# Mutation proof

Design law 9: a green test can guard a bug. Every test must fail when the code that
it claims to watch breaks. This record proves it for the suite of version 0.1.0.

Method, on 2026-09-04: one mutation per run. Break one line, run
`python3 -m unittest discover -s tests -t .`, record the tests that turn red, restore
the line, run the suite again and check that it is green. The script that did it is
not part of the product: it edits the source. The measure is HOW MANY tests turn red,
not whether one does. Baseline: 106 tests, 0 red. After the last restore: 106 tests,
0 red.

| id | file | mutation | tests that turned red |
|---|---|---|---|
| M01 | `harness/board.py` | done on an eye task no longer needs a verdict | 2 — `BoardTest.test_cli_round_trip`, `BoardTest.test_done_on_eye_task_needs_verdict` |
| M02 | `harness/board.py` | ready() ignores open blockers | 1 — `BoardTest.test_next_skips_blocked_and_ranks_due_then_priority` |
| M03 | `harness/manifest.py` | doctor never compares a checksum | 2 — `ManifestTest.test_adopt_and_restore`, `ManifestTest.test_edited_owned_file_is_damaged_and_names_the_fix` |
| M04 | `harness/clock.py` | days_remaining is off by one | 4 — `BoardTest.test_board_text_is_computed_and_names_next`, `ClockTest.test_clock_report_text`, `ClockTest.test_days_remaining_follows_today`, `DashboardTest.test_serve_answers_health_and_board` |
| M05 | `harness/state.py` | observe appends the same stock twice in a day | 1 — `StateTest.test_observe_once_per_stock_per_day` |
| M06 | `harness/hooks.py` | pre-write never recognises a state folder | 1 — `HookTest.test_pre_write_denies_new_file_in_state_folder` |
| M07 | `harness/rag.py` | never-synced is a warning instead of broken | 1 — `RagCanaryTest.test_never_synced_is_broken` |
| M08 | `harness/templates/infra/rag/agent/agent.py` | an `Indexed:` line is recorded without its collection header | 1 — `AgentParserTest.test_parse_indexed_reads_per_collection_lines` |
| M09 | `harness/session.py` | front numbers start at 0 | 1 — `SessionTest.test_front_rows_parse_and_number_per_brief` |
| M10 | `harness/ports.py` | every port reads as free | 2 — `PortsTest.test_cli_exit_code_reflects_a_taken_port`, `PortsTest.test_free_and_taken` |
| M11 | `harness/ceremonies.py` | the retro ignores the sprint dates | 1 — `CeremonyTest.test_retro_reads_the_journal_inside_the_dates` |
| M12 | `harness/scaffold.py` | init overwrites a file that exists | 2 — `ManifestTest.test_init_is_idempotent`, `ScaffoldTest.test_upgrade_rewrites_unchanged_and_keeps_edited` |
| M13 | `harness/frontmatter.py` | list items are dropped | 5 — `BoardTest.test_check_finds_shape_errors`, `BoardTest.test_check_flags_done_with_open_blocker`, `BoardTest.test_next_skips_blocked_and_ranks_due_then_priority`, `FrontMatterTest.test_dump_round_trip`, `FrontMatterTest.test_parse_scalars_lists_and_body` |
| M14 | `harness/dashboard.py` | an unmeasured age is stored as 0 | 1 — `DashboardTest.test_build_db_is_a_cache_with_built_at` |
| M15 | `harness/board.py` | check accepts any work size | 1 — `BoardTest.test_check_finds_shape_errors` |
| M16 | `harness/board.py` | check ignores a priority with no provenance | 1 — `BoardTest.test_priority_without_provenance_turns_check_red` |
| M17 | `harness/hooks.py` | the pre-write hook never sees a priority line | 1 — `HookTest.test_pre_write_denies_priority_by_hand` |
| M18 | `harness/help.py` | help skills prints a fixed list and never reads the tree | 1 — `HelpTest.test_skills_are_read_from_the_tree_not_from_a_list` |
| M19 | `harness/help.py` | an unknown help topic returns the overview instead of an error | 1 — `HelpTest.test_unknown_topic_exits_1_and_names_every_topic` |
| M20 | `harness/help.py` | help names a path without a check that the path exists | 1 — `HelpTest.test_help_runs_before_init_and_marks_the_missing_paths` |
| M21 | `harness/scaffold.py` | the manifest records the adopter's first task | 3 — `SeedTaskTest.test_init_writes_the_first_task_and_the_manifest_ignores_it`, `SeedTaskTest.test_doctor_stays_sound_after_the_first_task_moves`, `ScaffoldTest.test_cli_profile_and_doctor` |
| M22 | `harness/scaffold.py` | init writes the first task again after the adopter moves it | 1 — `SeedTaskTest.test_init_never_writes_the_first_task_twice` |
| M23 | `harness/help.py` | help eye hard-codes the eye values | 1 — `HelpTest.test_eye_topic_follows_harness_board_eye` |
| M24 | `harness/help.py` | help board hard-codes the states | 1 — `HelpTest.test_board_topic_follows_harness_board_states` |
| M25 | `harness/manifest.py` | only_missing_seeded accepts any problem, whatever its kind | 2 — `ReseedTest.test_a_damaged_owned_file_is_never_only_missing_seeded`, `ReseedTest.test_session_open_never_hides_a_damaged_owned_file` |
| M26 | `harness/manifest.py` | doctor never marks the kind of a missing file | 2 — `ReseedTest.test_doctor_marks_a_missing_seeded_file`, `ReseedTest.test_session_open_writes_the_missing_seeded_files_again` |
| M27 | `harness/session.py` | session open ignores a repository that keeps its board out of git | 1 — `ReseedTest.test_session_open_writes_the_missing_seeded_files_again` |
| M28 | `harness/scaffold.py` | init rewrites settings.json when no key changed | 1 — `ReseedTest.test_reseed_leaves_a_compact_settings_file_alone` |

M18 to M24 ran on 2026-09-05 for the `help` command and the seeded first task.
Baseline 123 tests, 0 red. After the restore: 123 tests, 0 red.

M28 records a defect that the reseed exposed. `_merge_hooks` wrote
`.claude/settings.json` on every `init`, and `json.dumps` expands a compact array. A
fresh clone ran `session open`, the reseed ran `init`, and `git status` reported a diff
that nobody made. The function now writes the file only when a key changes (law 12).

M25 to M27 ran on 2026-09-05 for the reseed that `session open` runs. This repository
keeps its own board out of git, so a clone lacks every seeded file. Baseline 130 tests,
0 red. After the restore: 130 tests, 0 red. M25 is the guard that matters: a reseed that
fires on any damage hides a wrong checksum behind a file that `init` writes again.

`HelpTest.test_overview_names_no_path_that_init_does_not_create` turned red once for
real on 2026-09-05, with no mutation. `help` named `docs/DESIGN-LAWS.md` and offered
`init` as the fix. `init` never installs that file: the twelve laws travel to the
adopter in short form inside `CLAUDE.md`, and the full record stays in the harness
repository. This repository holds `docs/DESIGN-LAWS.md`, so the path existed here and
the text looked correct. Law 3 names this trap. The test runs on a fresh repository,
so it measured what this repository hides. The `help` text now states where the full
record lives, and it offers no fix that `init` cannot deliver.

M23 and M24 exist because the first version of the two topic tests was weak. That
version asserted that the output holds `NONE`, `GLANCE`, and `RUN`. A hard-coded copy
of the same three words passed it. The test now patches `harness.board.EYE` and
`harness.board.STATES` with a probe value, so it measures the coupling and not the
words. Law 9 names this trap: a green test can guard a bug.

M16 and M17 ran on 2026-09-04 after the user chose enforcement for `priority`
(proposal P17). Baseline 110 tests, 0 red. After the restore: 110 tests, 0 red.

## The gap that the method found

M08 turned **0** tests red on its first run. The fixture of
`test_parse_indexed_reads_per_collection_lines` had an `Indexed:` line after every
collection header, so a parser that ignores the header still produced the same
dictionary. The fixture made the guarded operation trivial. The fix added a final
`Indexed:` total line with no header, which qmd prints at the end of a run. The
mutation then turned 1 test red. The test comment records this.

## What this record does not prove

- It does not prove that every line is watched. Fifteen lines were broken, out of
  about 2,300 lines of product code.
- It does not prove that the tests measure the right thing. A test that reads the
  wrong place turns red for the wrong reason too.
- The policy tests (`tests/test_policy.py`) are measured on the files, not on a
  mutation. The `wsl ` guard turned red once for real on 2026-09-04: its own
  docstring carried the string. The docstring no longer does.
