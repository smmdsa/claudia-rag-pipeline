# Proposals

Each proposal names the gap, the source file or measurement that shows it, and the
status. `implemented` means the code exists and a test covers it. `written` means the
proposal waits for a decision or for data.

## P1. A sprint gets a clock — implemented

**Gap.** Source B has no clock. `sprints/sprint-004/sprint-004.md` declares `started:
2026-08-24` and no end. `tools/sprint.mjs` never reads a date. A sprint ends when
someone says so, and nobody says so.

**Change.** A sprint sheet declares `starts` and `ends`. `harness board` prints the days
that remain, computed from today. `check` warns on an overdue sprint with open tasks.
`ceremony review` lists them. No command moves a date. Test: `tests/test_clock.py`.

## P2. Front numbers are per brief, and the tool says so — implemented

**Gap.** Source A numbers the fronts inside each brief
(`.claude/skills/session-start/SKILL.md`, step 2B.5). The skill states that a number
from a past session is not valid. The user still references old numbers, and the agent
guesses.

**Change.** `harness session open` numbers the rows of `docs/ACTIVITY.md` in print order
and prints the sentence *"Numbers are per brief. Name a front by its text in a later
session."* The row text is the stable reference. Test: `tests/test_session.py`.

## P3. The harness measures itself — implemented

**Gap.** Neither source measures whether the harness works in the repository that hosts
it. Source A found its index dead after 31 days. Source B found 21 dead command blocks
in a skill.

**Change.** `harness doctor` checks the manifest, the checksum of every owned file, the
hooks in `.claude/settings.json`, and the version. `tests/test_policy.py` fails on the
string `wsl ` in any executable file and on any third-party import. The session opener
runs doctor at step 0. Tests: `tests/test_manifest.py`, `tests/test_policy.py`.

## P4. An uninstall path — implemented

**Gap.** Neither source can remove itself. Files accumulate and nobody knows which ones
the harness put there.

**Change.** The manifest lists every installed file with its kind. `harness uninstall`
removes the owned files that still match their checksum, keeps every seeded or edited
file, and prints what it kept. `--dry-run` prints the plan. Test: `tests/test_scaffold.py`.

## P5. A version and a migration table — implemented

**Gap.** Neither source states a version. A change to a template silently diverges from
the installed copy.

**Change.** `harness/__init__.py` holds `VERSION`. The manifest records the installing
version. `harness upgrade` rewrites the unchanged owned files, reports the edited ones,
and runs the migration steps in `scaffold.MIGRATIONS` between the two versions.
Test: `tests/test_scaffold.py`.

## P6. The verdict queue reports its age — implemented

**Gap.** Source B caps the queue at 5 (`.system/desired.json`) and never reports how
long an item waited. `tools/pipeline_state.mjs` names `latencia_qa_dias` as missing
instrumentation.

**Change.** `harness state` reports `eye_queue_age_days`: the age of the oldest task in
`in-progress` with an eye, measured from the git commit that moved it there. When the
move is not committed the stock prints `not measured` with the reason. The dashboard
shows the age per task. Test: `tests/test_state.py`.

## P7. The verdict is enforced by the tool — implemented

**Gap.** Source B enforces "an eye task never closes without a human verdict" in
`.claude/skills/sprint/SKILL.md`, rule 2. A rule in a skill has no exit code.
`tools/sprint.mjs` moves the file on request.

**Change.** `harness done` refuses an eye task without `--verdict`. The tool writes the
verdict with the date into the task file. `check` reports a done eye task with no
verdict. Test: `tests/test_board.py`.

## P8. Ids carry no epic — implemented

**Gap.** Source B encodes the epic in the id (`TASK-0207` is the seventh task of epic
02). The epic then lives in two places, the id and the folder. A task that moves to
another epic keeps a false id.

**Change.** Ids are global and sequential. The folder gives the epic. `harness new task`
computes the next id from the tree. Test: `tests/test_board.py`.

## P9. Targets carry provenance, and the tool writes them — implemented

**Gap.** Source B keeps provenance by hand in `desired.json` (`procedencia`). A hand
edit forgets it.

**Change.** `harness target set <stock> <value> --by <who> --why "<text>"` is the only
writer. The pre-write hook denies a hand edit of `targets.json`. Test:
`tests/test_state.py`.

## P10. The RAG companion is Python — implemented

**Gap.** Source A runs the companion in JavaScript under bun
(`infra/qmd/agent/agent.mjs`). The rest of the tooling is Python. Two languages, two
test runners, two skill sets.

**Change.** `infra/rag/agent/agent.py` uses the standard library. The image adds
`python3` from the distribution. The parsing of the `Indexed:` lines has a unit test
that runs with no container. Test: `tests/test_rag.py`.

## P11. Observations go to the journal, decisions go to escalations — implemented

**Gap.** Source B writes escalations by hand. Nothing measures the gap between a target
and the current value on a schedule.

**Change.** The `SessionEnd` hook and `session close` append one `observation` line per
missed target. The same stock on the same day appends once. The retro reads them. The
agent writes the decision nowhere. Test: `tests/test_hooks.py`.

## P12. The backlog is a folder, not a document — implemented

**Gap.** Source B keeps the backlog in `docs/BACKLOG.md` with a 200-line cap, and the
cap broke once at 1,881 lines. A document that mixes tasks and narrative cannot be
counted.

**Change.** `work/backlog/` holds task files with the same front matter as sprint tasks.
`ceremony plan` counts them and sums their sizes. Narrative goes to `work/ROADMAP.md`.

## P17. `priority` carries its provenance, and the tool holds the rule — implemented

**Gap.** The first report of 2026-09-04 named it: the rules forbid the agent to set
`priority`, and the tool accepted a hand-written `priority: 1` from anyone. Source B,
`sprints/sprints.md`, records the day the board ranked by epic number and named the
wrong epic. The user chose enforcement.

**Where the provenance lives, and why.** In the task front matter: `priority`,
`priority-by`, `priority-date`, `priority-why`. Not in `.harness/targets.json`. Three
reasons. A task is read in one place, its file; a second file with a list of ids is a
second list, and law 2 says two lists diverge. The task file travels with `git mv`, so
the history shows who set the priority and in which commit, next to the move. And the
pre-write hook already guards task files, so the guard for a hand-written `priority`
line lands where the other guards are. `targets.json` keeps what is not a task: the
stocks.

**Change.** `harness priority <id> --by <who> --why "<words>"` is the only writer; it
refuses `--by agent` and an empty reason, and `--clear` removes the four fields. `new
task` takes no priority. `check` exits 1 on a priority with no author or no date, with
the agent as author, or with a date that is not `YYYY-MM-DD`; the error names the task
and the command. The pre-write hook denies a `Write` or `Edit` that adds, removes, or
changes a `priority*:` line in a task file. Tests: `tests/test_board.py`,
`tests/test_hooks.py`. Mutations M16 and M17 in `docs/MUTATION.md`.

## P13. A front board row needs a date — written

**Gap.** Source A's `docs/ACTIVITY.md` carries a free-text `Últ. toque` column. The
staleness check parses it by hand.

**Proposal.** Add a machine-readable `touched: YYYY-MM-DD` column and let `session open`
flag rows over 14 days. The seeded `docs/ACTIVITY.md` has the column. The parser reads
it when present. The flag is not implemented, because the 14-day limit is a target and
the user has not declared it. Declare it with `harness target set front_stale_days 14`.

## P14. Cost per session from the transcripts — written

**Gap.** Source A reads cost and tokens from `~/.claude/projects/<slug>/*.jsonl`
(`collect-metrics.py`). That format is not documented and changed once during the
measurement.

**Proposal.** Keep it out of the product until the transcript format has a contract.
A stock that reads an undocumented file breaks in silence, which is law 3.

## P15. The dashboard serves the tree, not a stored number — implemented

**Gap.** Source A's dashboard injects metrics into a template at build time
(`build-dashboard.py`). The page then shows the build time as the truth for as long as
it stays open.

**Change.** The container rebuilds the cache on a timer and the page shows `built_at`.
The static page shows the same field. A reader sees the age of what they read.

## P16. One test proves each hook without Claude Code — implemented

**Gap.** Neither source tests a hook. A hook that fails to parse stdin fails in silence.

**Change.** `tests/test_hooks.py` feeds the documented stdin payloads to each hook and
asserts the exit code and the JSON decision. The payload shapes come from the Claude
Code hooks reference, and `docs/HOOKS.md` records them.
