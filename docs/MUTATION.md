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
