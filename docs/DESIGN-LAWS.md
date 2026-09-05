# The design laws, and their measured origins

Each law names a defect that cost time in one of the two source repositories.
Source A is an agent and RAG harness for a CAD application. Source B is a folder
board for a game. Both are private. The measurements are quoted from their files.

## 1. The folder tree is the truth. The board is computed, never stored.

**Origin.** Source B, `sprints/sprints.md`: *"A stored number rots in silence, and
then it reads as a measurement. This project measured that failure four times."* The
backlog document of source B reached 1,881 lines, and the session opener read 26% of
it while it called itself the state.

**In the code.** `board.scan` reads the tree on every call. No command writes a count
into a file. The dashboard database is a cache with `built_at` in its `meta` table.

## 2. A rule lives in exactly one place.

**Origin.** Source B, `.claude/skills/sprint/SKILL.md`: the skill points at
`sprints/sprints.md` and states *"if this skill and that file said the same thing in
other words, they would diverge"*. Source B's opener once named four trackers as
active, and the backlog no longer named two of them.

**In the code.** The skills point at `CLAUDE.md` and `work/README.md`. The template
of the rules is one file, `harness/templates/CLAUDE.md`. `init` writes it to one of
two paths and records which.

## 3. A path that still exists does not prove that the path is correct.

**Origin.** Source A, `.claude/scripts/rag-health.py` header: the collections pointed
at the abandoned `/mnt/c` tree for 31 days. The tree existed, so every existence
check passed. Every search answered from a dead tree.

**In the code.** `doctor` parses `settings.json` and checks that each hook command
calls the harness. `rag health` reads `/state` from the running service. `ports`
binds each port.

## 4. Ask what number moves if the system dies right now.

**Origin.** Source A, `infra/qmd/agent/agent.mjs`: the canary measured the mtime of
the newest source file and called it freshness. a companion repository reported 119 h
while `qmd update` had covered it minutes before. The canary failed in both
directions: false alarm, and blind when the indexer died.

**In the code.** `infra/rag/agent/agent.py` records the per-collection `Indexed:`
line of every `qmd update`. The age of that record is freshness. The file date is
reported as `content` and never called freshness.

## 5. A command that exits 0 on error hides the error.

**Origin.** Source A, `session-close/SKILL.md` step 8B: *"`qmd update` exits 0 even
when it fails. Measured: on a collection whose path does not exist it prints `code:
"ENOENT"` and returns exit 0."*

**In the code.** The agent parses the transcript before the exit code decides
anything. A collection with no `Indexed:` line goes to `never-synced` and the canary
reports it as broken.

## 6. Never write the string `wsl ` inside an executable file.

**Origin.** Source A: `.mcp.json` started a `wsl` wrapper that does not exist inside
WSL. That killed the search index for 31 days. On 2026-09-04 the same wrapper killed
21 command blocks in a second skill. Source A's session document of that day:
*"the same failure, in another file"*.

**In the code.** `tests/test_policy.py` fails on the string in any executable file of
the product. The product derives every path with `python3 -m harness env`.

## 7. A default value must never look like a measurement.

**Origin.** Source A, `rag-health.py` comment: *"this branch never read it and
`render` printed a hardcoded 0 while the index held 260."* The 0 came from a
dictionary default.

**In the code.** Every stock in `state.measure` is a number or `None` with a
`reason`. The canary prints `not measured` for a missing orphan count. The dashboard
prints `not measured (move not committed)` for an unknown age.

## 8. The agent declares nothing that the user must own.

**Origin.** Source B, `.system/desired.json`: *"the desired levels are declared by the
USER, never the agent."* And `sprints.md` on `priority`: *"on 2026-09-04 the board
and the user disagreed, and the board was wrong."* The tool ranked by epic number
because that was the only order it knew.

**The account, from source B `sprints/sprints.md`.** On 2026-09-04 the user closed a
session and named the localization epic (`EP-31`) as what opens the next one. `next`
answered `TASK-2801`, because 28 < 31 and the epic number was the only order the tool
knew. The backlog then carried a sentence: *"the board will tell you EP-28, he said
EP-31"*. That sentence is a second list, and two lists diverge. Source B added
`priority: 1` as a field, set *"from what he SAID, in his words, and never from what
the agent thinks matters"*. The rule lived in prose. The tool accepted any value from
anyone.

**In the code.** `target set` needs `--by` and `--why`. The pre-write hook denies a
hand edit of `targets.json`. `done` on an eye task needs `--verdict`. `escalate`
writes the observation and leaves the decision empty. `priority` follows the same
shape since 0.1.0 (decision of the user on 2026-09-04): `harness priority <id> --by
user --why "..."` is the only writer and records the author, the date, and the words;
`check` exits 1 on a priority with no author, no date, or the agent as author; the
pre-write hook denies a `priority` line written by hand into a task file.

## 9. A green test can guard a bug.

**Origin.** Source A's durable memory, *"a green test can be guarding the bug"*,
recorded three times. The third time the harness that hid it was pre-written in the
plan. Fifteen forms of false green are listed there.

**In the code.** Every test module header records a mutation: one line was broken,
the suite ran, and the tests that turned red are named. `docs/MUTATION.md` holds the
full record.

## 10. Two sizes, not one.

**Origin.** Source B, `sprints.md`: *"The QA queue reached 11 items against a cap of
5, and 7 builds shipped without a human verdict. A board that counts only effort lets
an agent stack work that nobody can validate."*

**In the code.** Every task carries `work` and `eye`. `check` rejects a missing
size. `done` refuses an eye task without a verdict. `state` reports the queue and its
age.

## 11. Every port must be checked before use.

**Origin.** This machine, 2026-09-04: ports 8181 and 8182 were taken by source A's
stack while the product was designed. A second stack with the same defaults fails
with a message that names neither the port nor the holder.

**In the code.** `ports.py` binds each port. `up.sh` runs it before `docker compose
up`. `dashboard serve` refuses a taken port and names the variable that overrides it.

## 12. Read before you write.

**Origin.** Source A's global rules, and the case of the exporter: the front board
reported a front as *"plan closed, not implemented"* while it had 15 commits in a
worktree that nobody read.

**In the code.** `init` never overwrites a file. `restore` prints the diff before it
writes. `session draft` refuses to overwrite an existing document.
