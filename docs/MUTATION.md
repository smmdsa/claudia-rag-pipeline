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
| M29 | `harness/stack.py` | start builds the image instead of starting the container | 2 — `StackTest.test_start_never_builds`, `StackTest.test_start_reports_what_it_started` |
| M30 | `harness/stack.py` | start builds a container that does not exist | 1 — `StackTest.test_start_refuses_to_build_a_container_that_does_not_exist` |
| M31 | `harness/stack.py` | status calls docker before it reads the compose file | 1 — `StackTest.test_a_missing_compose_file_reports_and_never_calls_docker` |
| M32 | `harness/session.py` | session open starts the stack whatever the canary says | 1 — `SessionStackTest.test_a_green_canary_never_calls_docker` |
| M33 | `harness/session.py` | session open ignores --no-stack | 1 — `SessionStackTest.test_no_stack_never_calls_docker` |
| M34 | `harness/board.py` | find_epic returns the first match and never reports the ambiguity | 1 — `EpicIdTest.test_a_repeated_epic_id_names_every_candidate` |
| M35 | `harness/board.py` | the verdict lookup ignores the sprint of the task | 1 — `EpicIdTest.test_a_verdict_lands_in_the_sheet_of_its_own_sprint` |
| M36 | `harness/board.py` | new sprint accepts any id, whatever its shape | 1 — `EpicIdTest.test_new_sprint_refuses_an_id_that_is_not_sprint_nnn` |
| M37 | `harness/board.py` | new sprint overwrites a sprint that exists | 1 — `EpicIdTest.test_new_sprint_refuses_an_id_that_exists` |
| M38 | `harness/stack.py` | the port check ignores who holds the port | 1 — `PortTest.test_a_port_that_this_stack_holds_is_not_a_conflict` |
| M39 | `harness/stack.py` | a stopped container still claims its published port | 1 — `PortTest.test_a_stopped_container_does_not_hold_its_port` |
| M40 | `harness/board.py` | _append_section writes at the end of the file, and never at the end of the section | 4 — `BoardTest.test_append_section_writes_inside_a_section_in_the_middle`, `BoardTest.test_append_section_accumulates_in_order`, `BoardTest.test_append_section_keeps_a_deeper_header_inside_the_section`, `BoardTest.test_done_writes_the_epic_verdict_under_its_own_header` |
| M41 | `harness/mcp.py` | an index that started after the agent still reads as a live link | 1 — `LinkTest.test_an_index_that_started_later_is_stale` |
| M42 | `harness/mcp.py` | the elapsed time of the client is read as an absolute time | 1 — `AncestorTest.test_finds_the_client_above_the_shell` |
| M43 | `harness/dashboard.py` | the cache is never stale, so the page answers from an old reading | 2 — `DashboardTest.test_a_move_makes_the_cache_stale`, `DashboardTest.test_the_page_reads_a_move_with_no_wait` |
| M44 | `harness/ports.py` | port_for ignores the env file that docker compose reads | 2 — `PortsTest.test_port_for_reads_the_env_file_that_docker_compose_reads`, `PortsTest.test_stack_ports_check_the_port_that_docker_publishes` |
| M45 | `infra/rag/agent/agent.py` | the agent never runs the cleanup, so the orphan rate grows all day | 1 — `AgentCleanupTest.test_cleanup_runs_when_the_rate_passes_the_threshold` |
| M46 | `infra/rag/agent/agent.py` | the agent vacuums the database on every update, threshold or not | 2 — `AgentCleanupTest.test_a_quiet_day_costs_no_cleanup`, `AgentCleanupTest.test_a_rate_that_nobody_measured_is_not_a_rate_of_zero` |
| M47 | `infra/rag/agent/agent.py` | an index that cannot answer reads as a clean index, and 0.0 looks measured | 2 — `AgentCleanupTest.test_a_rate_that_nobody_measured_is_not_a_rate_of_zero`, `AgentCleanupTest.test_an_empty_index_never_divides_by_zero` |
| M48 | `infra/rag/agent/agent.py` | a failed embed still reaches the cleanup, which removes the vectors it did not write | 1 — `AgentCleanupTest.test_a_failed_embed_stops_before_the_cleanup` |
| M49 | `harness/rag.py` | a timeout reads as a refused connection, so a slow index is a dead service | 3 — `UpdateReportTest.test_http_json_names_a_timeout_and_a_refusal_apart`, `UpdateReportTest.test_a_slow_answer_is_not_a_dead_service`, `UpdateReportTest.test_a_timeout_reaches_the_close_line_and_never_says_FAILED` |
| M50 | `harness/rag.py` | a timeout reports `ok: False`, so the close prints FAILED for a healthy stack | 2 — `UpdateReportTest.test_a_slow_answer_is_not_a_dead_service`, `UpdateReportTest.test_a_timeout_reaches_the_close_line_and_never_says_FAILED` |
| M51 | `infra/rag/agent/agent.py` | `POST /update` answers after the steps run, so a 60 s embed times out the client | 2 — `AgentStartUpdateTest.test_start_update_answers_before_the_steps_finish`, `AgentStartUpdateTest.test_a_second_start_never_runs_two_updates_at_once` |
| M52 | `infra/rag/agent/agent.py` | the reservation is released before the run is recorded | 1 — `AgentStartUpdateTest.test_the_record_lands_before_the_reservation_is_released` |
| M53 | `infra/rag/agent/agent.py` | `start_update` never checks the reservation, so two runs embed at once | 1 — `AgentStartUpdateTest.test_a_second_start_never_runs_two_updates_at_once` |
| M54 | `harness/rag.py` | a timeout reads as a started run, so the close reports work that nobody proved | 2 — `TimeoutIsNotStartedTest.test_a_timeout_with_no_reader_is_not_a_started_run`, `UpdateReportTest.test_a_slow_answer_is_not_a_dead_service` |
| M55 | `harness/rag.py` | an HTTP error and a body that is not JSON read as a dead stack | 2 — `AnsweredIsNotDownTest.test_an_http_error_is_an_answer`, `AnsweredIsNotDownTest.test_a_body_that_is_not_json_is_an_answer` |
| M56 | `harness/rag.py` | the canary calls a slow index a dead stack, and tells the user to start it | 1 — `TimeoutIsNotStartedTest.test_the_canary_names_a_timeout_and_never_calls_the_stack_down` |
| M57 | `infra/rag/agent/agent.py` | the reservation leaks when the thread does not start, so every later run is skipped | 1 — `AgentStartUpdateTest.test_a_thread_that_never_starts_frees_the_reservation` |
| M58 | `scripts/contributors.py` | an API that gives no answer empties the list, and removes a name a person earned | 1 — `ContributorBlockTest.test_no_answer_leaves_every_name_in_place` |
| M59 | `scripts/contributors.py` | a bot account is thanked as a person | 1 — `ContributorBlockTest.test_a_bot_never_appears` |
| M60 | `scripts/contributors.py` | `--check` writes the file instead of reporting the stale list | 1 — `ContributorBlockTest.test_check_reports_a_stale_list_and_writes_nothing` |
| M61 | `scripts/contributors.py` | the writer replaces the whole README, and not the block | 2 — `ContributorBlockTest.test_a_new_name_lands_in_the_block`, `ContributorBlockTest.test_check_is_quiet_when_the_list_is_current` |
| M62 | `scripts/contributors.py` | an empty list is written, and it removes every earned name | 3 — `ContributorBlockTest.test_an_empty_list_leaves_every_name_in_place`, `ContributorBlockTest.test_an_answer_of_only_bots_leaves_every_name_in_place`, `ContributorBlockTest.test_an_empty_list_never_reports_a_stale_file` |
| M63 | `scripts/contributors.py` | a message names the repository slug instead of the API url | 1 — `ContributorBlockTest.test_a_message_names_the_api_url_and_not_the_slug` |

M38 and M39 ran on 2026-09-05, after `./infra/rag/up.sh` refused to run on a stack that
was already up. Baseline 151 tests, 0 red. After the restore: 151 tests, 0 red.
`harness ports` binds a port to test it, so it cannot name the holder. The script told
the user to override a port that nothing else wanted.

M34 to M37 ran on 2026-09-05, after the second sprint of this repository exposed the
defect. Baseline 147 tests, 0 red. After the restore: 147 tests, 0 red.

M35 is the defect that the board found by running. Every sprint numbers its epics from
EP-01, so sprint-000 and sprint-001 both held an `EP-01`. `find_epic` walked the
sprints in order and returned the first match. `move` used it to pick the epic sheet
that receives a verdict, so closing a task in sprint-001 wrote the user's words into
the epic sheet of sprint-000. `check` stayed green: the shape of the tree was correct,
and the words were in the wrong file. This is the same shape as issue #1, which the
adopter found on 2026-09-05: a verdict that lands in the wrong place, under a test that
asserts only that the string is present.

M29 to M33 ran on 2026-09-05 for the stack repair that `session open` runs. Baseline
141 tests, 0 red. After the restore: 141 tests, 0 red. The suite needs no daemon: every
test replaces `harness.stack.sh` and measures the commands that the module builds.

`StackTest.test_an_unknown_stack_name_is_an_error` turned red once for real on
2026-09-05, with no mutation. `status` read `STACKS[name]` to build its report before
`compose_file` checked the name, so an unknown stack raised `KeyError` and not the
error text that names the two stacks. Rule 11 of the writing rules: an error says what
happened, why, and what to do next. A `KeyError` says none of the three.

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
- A test that never runs guards nothing, and no mutation finds it.
  `tests/test_help.py` called `unittest.main()` three lines above `ReseedTest`, so
  `python3 -m tests.test_help` ran 14 tests and `python3 -m unittest tests.test_help`
  ran 20. Six tests were invisible to anyone who ran the file as a script. The count of
  the two commands must agree. The reviewer of PR 2 found this one, and no mutation
  could.
- The policy tests (`tests/test_policy.py`) are measured on the files, not on a
  mutation. The `wsl ` guard turned red once for real on 2026-09-04: its own
  docstring carried the string. The docstring no longer does.
