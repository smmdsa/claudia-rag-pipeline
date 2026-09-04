# Architecture

This document names every component, every port, and every contract of the harness.
The harness is a Python package plus files that the package installs into a repository.
The package uses the Python standard library only. The Docker images carry the only
third-party code, and a lockfile pins that code.

## 1. The shape

```text
<your repository>/
├── harness/                    the Python package. Copy this directory to install.
│   ├── __main__.py             `python3 -m harness <command>`
│   ├── cli.py                  the command table
│   ├── manifest.py             .harness/manifest.json, checksums, doctor
│   ├── scaffold.py             init, upgrade, uninstall, adopt, restore
│   ├── frontmatter.py          the front matter reader and writer
│   ├── board.py                the work tree: scan, board, next, moves, check, new
│   ├── clock.py                sprint dates and the days that remain
│   ├── ceremonies.py           plan, triage, review, retro
│   ├── state.py                computed stocks against declared targets
│   ├── journal.py              .harness/journal.jsonl
│   ├── session.py              session open and session close
│   ├── ports.py                port checks
│   ├── env.py                  the derived machine environment file
│   ├── profile.py              the project profile and the skill generator
│   ├── hooks.py                the hook entry points
│   ├── rag.py                  the RAG canary and the index configuration
│   ├── dashboard.py            the SQLite cache, the server, the static page
│   └── templates/              every file that `init` installs
├── .harness/                   the harness state
│   ├── manifest.json           version, profile, checksum list. The tool writes it.
│   ├── targets.json            targets. THE USER writes it, through `target set`.
│   ├── escalations.md          what the agent cannot decide. The agent appends.
│   ├── journal.jsonl           one line per session or observation. Append only.
│   └── env.local               machine paths. Derived. Git ignores it.
├── work/                       the work management system
│   ├── README.md               the rules of the board. One place.
│   ├── ROADMAP.md              the long horizon. The user writes it.
│   ├── backlog/                tasks that belong to no sprint
│   ├── templates/              task.md, epic.md, sprint.md
│   └── sprints/sprint-NNN/
│       ├── sprint-NNN.md       starts, ends, goal
│       ├── ceremonies/         the documents that the ceremonies write
│       └── epic-NN-slug/
│           ├── epic-NN-slug.md
│           ├── todo/           TASK-NNNN-slug.md
│           ├── in-progress/
│           └── done/
├── docs/
│   ├── ACTIVITY.md             the front board. Humans write rows. Sessions read them.
│   ├── session-log.md          one row per session
│   └── sessions/               one document per session
├── .claude/
│   ├── settings.json           permissions and hooks
│   ├── rules/harness.md        the rules, when CLAUDE.md already existed
│   ├── skills/                 session-start, session-close, board, ceremony,
│   │                           research, architecture-reader, end-user-impact
│   ├── agents/researcher.md    the read-only research agent
│   └── workflows/research.js   the 3-layer research workflow
├── infra/rag/                  the search index stack (Docker)
└── infra/board/                the board dashboard container (Docker)
```

## 2. The design laws that shape the code

`docs/DESIGN-LAWS.md` holds the twelve laws with their measured origins. These four
decide most of the structure:

| law | consequence in the code |
|---|---|
| 1. The tree is the truth | `board.py` stores nothing. Every command scans `work/` again. |
| 2. A rule lives in one place | Skills point at `work/README.md` and `CLAUDE.md`. They do not repeat rules. |
| 7. A default is not a measurement | Every computed value is a number or `None` with a `reason`. |
| 8. The agent declares nothing that the user owns | `targets.json` records who set each target and why. |

## 3. Components and contracts

### 3.1 The package and the entry point

`python3 -m harness <command>` is the single entry point. `cli.py` maps each command
to one function. Every read command accepts `--json`. Every command exits 0 on success.
`check` and `doctor` use exit codes as their verdict. The package needs Python 3.10 or
later. It imports only the standard library. The test `tests/test_policy.py` fails if a
module imports a third-party package, or if any executable file contains the string
`wsl ` followed by a space.

### 3.2 The manifest and the integrity gate

`.harness/manifest.json`:

```json
{
  "harness_version": "0.1.0",
  "created_at": "2026-09-04T20:11:03+00:00",
  "profile": { "architecture": "", "languages": [], "purpose": "", "end_user": "" },
  "rules_path": "CLAUDE.md",
  "files": {
    "work/README.md": { "kind": "owned", "sha256": "..." },
    "work/ROADMAP.md": { "kind": "seeded" }
  }
}
```

Two kinds of installed file:

| kind | who edits it | doctor check |
|---|---|---|
| `owned` | the harness | the file exists and its checksum matches the manifest |
| `seeded` | the project | the file exists |

`harness doctor` reports one of three states and exits with the matching code:

| exit | state | meaning |
|---|---|---|
| 0 | sound | the manifest exists and every owned file matches |
| 1 | damaged | a file is missing or edited. Doctor names the file and the fix. |
| 2 | not initialised | no manifest. The fix is `harness init`. |

Doctor also measures live signals, not only checksums: the hooks in `.claude/settings.json`
still call the harness, and the manifest version matches the package version.

`harness adopt <file>` records a local edit into the manifest. `harness restore <file>`
writes the template back. Both print the diff first.

### 3.3 The work tree

`board.py` scans `work/sprints/*/epic-*/{todo,in-progress,done}/*.md` and `work/backlog/*.md`.
The folder gives the state. The front matter gives the fields:

| field | values | required |
|---|---|---|
| `id` | `TASK-NNNN`, unique across the tree | yes |
| `title` | text | yes |
| `work` | `XS S M L XL` | yes |
| `eye` | `NONE GLANCE RUN` | yes |
| `owner` | `agent` (default) or `user` | no |
| `due` | `YYYY-MM-DD` | no |
| `priority` | `1`, set from the user's words | no |
| `blocked-by` | list of task ids | no |
| `needs-decision` | a decision id | no |
| `refs` | list of paths or links | no |

Ids are global and sequential. Source B encoded the epic number inside the id. That
stores the epic twice, in the id and in the folder. The folder is the truth, so the id
carries no epic.

Moves use `git mv`. When the repository has no git, the tool falls back to a rename and
says so. `done` on a task with `eye: GLANCE` or `eye: RUN` needs `--verdict "<words>"`.
The tool writes a `## Verdict` section into the task file with the date. Without the
flag the move does not happen. `check` reports a done eye task without a verdict as an
error.

`check` measures the shape of the tree: unique ids, valid sizes, blockers that exist, a
done task with an open blocker, a done eye task with no verdict, a sprint with `ends`
before `starts`, and the work-in-progress cap from `targets.json`. `check` never
measures whether a task is correct.

`next` ranks ready tasks by `due`, then `priority`, then sprint order, then epic order,
then id. Ready means: in `todo`, every blocker done, no open decision. Tasks with
`owner: user` print first, because the agent cannot do them.

### 3.4 The clock

A sprint sheet declares `starts` and `ends`. `clock.py` computes the days that remain
from today. Nothing stores that number. A sprint whose `ends` passed with open tasks is
overdue. `board`, `check`, and `review` report it. No command moves a date.

### 3.5 The ceremonies

Each ceremony reads measured data and writes one document with an agenda and open
questions. The answers are the user's. A ceremony never writes a verdict.

| command | reads | writes |
|---|---|---|
| `ceremony plan` | backlog, roadmap, targets | candidate list with work and eye totals |
| `ceremony triage` | backlog, git age of each file | tasks with missing fields, old tasks |
| `ceremony review` | the sprint tree, the clock | done, open, awaiting verdict, overdue |
| `ceremony retro` | `journal.jsonl` inside the sprint dates | sessions, closed vs opened eye work, surprises |

The documents go to `work/sprints/<sprint>/ceremonies/<date>-<name>.md` with `--write`.

### 3.6 Targets, state, and escalations

Three files, three owners. `docs/DESIGN-LAWS.md` law 8 states why.

- `.harness/targets.json`: the user declares targets with `harness target set`. Every
  target records `decided_by`, `date`, and `why`.
- `harness state`: computes every stock on each run and prints current, target, and gap.
  A stock that the tool cannot measure prints `not measured` with the reason.
- `.harness/escalations.md`: the agent appends an observation and a measurement when a
  question is above its authority. The agent never writes the decision.

Stocks: `wip`, `eye_queue`, `eye_queue_age_days`, `overdue_sprints`, `backlog_size`,
`user_owned_open`, `sessions_7d`, `qa_closed_7d`, `commits_7d`, `days_since_session`,
`dirty_files`.

### 3.7 The journal

`.harness/journal.jsonl` holds one JSON object per line. Two kinds:

```json
{"kind":"session","ts":"...","slug":"2026-09-04-2011","branch":"main","head":"abc1234","commits":3,
 "qa_closed":[{"id":"TASK-0007","verdict":"ok","how":"run"}],"qa_open":["TASK-0008"],
 "surprises":[],"failed":[]}
{"kind":"observation","ts":"...","stock":"eye_queue","current":7,"target":5,"gap":2}
```

The retro reads this file. The self-improvement hook appends observations.

### 3.8 The session pipeline

`harness session open` prints one brief: doctor result, RAG canary, elapsed time since
the last session, repository delta against the last journal line, the front board rows
numbered in print order, the sprint board summary, `next`, and the state gaps. The
numbers on the front board are per brief. The brief says so.

`harness session close --slug <slug>` checks that `docs/sessions/<slug>.md` exists and
holds the required sections, adds the row to `docs/session-log.md`, appends the journal
line, asks the RAG stack to re-index, and prints the report. The agent writes the
narrative. The tool never writes it.

Both commands run with no RAG stack. They print a warning and continue.

### 3.9 The hooks

`.claude/settings.json` calls `python3 -m harness hook <name>`:

| event | matcher | hook | behaviour |
|---|---|---|---|
| `SessionStart` | `startup\|resume\|clear\|compact` | `session-start` | runs doctor, prints the result into the context |
| `PreToolUse` | `Write\|Edit` | `pre-write` | denies a new file in a state folder, and a hand edit of the manifest, the journal, or the targets |
| `PreToolUse` | `Bash` | `pre-bash` | denies `mv`, `cp`, `rm`, and `git mv` on the work tree |
| `PostToolUse` | `Write\|Edit\|Bash` | `post-work` | runs `check` after a change under `work/` |
| `Stop` | | `stop` | reports open eye work with no verdict and overdue sprints |
| `SessionEnd` | | `session-end` | appends one observation per target that the state misses |

A denied call returns `hookSpecificOutput.permissionDecision: "deny"` with the reason.
`docs/HOOKS.md` holds the stdin contract of each event.

### 3.10 The project profile and the generated skills

`harness profile ask` asks four questions: architecture, languages, purpose, end user.
`harness profile set key=value` sets one answer without a prompt. The answers go into the
manifest. `harness skills generate` writes three project skills from the profile:
`project-map`, `project-user-impact`, and `project-conventions`. The holistic skills
`architecture-reader`, `end-user-impact`, and `research` read the profile with
`harness profile show --json`.

### 3.11 The research workflow

`.claude/workflows/research.js` ports the 3-layer harness of source A. Layer 1 runs
many small read-only agents with one question each. Layer 2 runs a few agents that
trace flows over the layer-1 evidence. Layer 3 runs one reviewer that audits the plan.
The script takes `question`, `antQuestions`, and `beeTasks` as arguments. It has no
project names inside.

### 3.12 The RAG stack

`infra/rag/docker-compose.yml` starts two services from one image:

| service | port (loopback only) | environment variable | role |
|---|---|---|---|
| `rag` | 8410 | `HARNESS_RAG_PORT` | the qmd MCP server over HTTP |
| `rag-agent` | 8411 | `HARNESS_RAG_STATE_PORT` | re-indexes on a timer, serves `/state`, `/health`, `/update` |

The image builds from `oven/bun` pinned by digest, installs `@tobilu/qmd` from the
lockfile with `--ignore-scripts`, and adds `python3` from the distribution. The agent is
`infra/rag/agent/agent.py`, standard library only. The GPU target adds CUDA and is
optional. CPU is the default.

The stack mounts the repository and the memory directory read only. The host paths come
from `.harness/env.local`. `infra/rag/up.sh` derives that file when it is missing and
checks the ports before `docker compose up`.

`harness rag health` reads `/state` and reports `RAG: OK`, `RAG: warnings`, or
`RAG: BROKEN` with exit 0, 1, or 2. It measures the last time `qmd update` covered each
collection, from the `Indexed:` lines that qmd prints. It never reads a file date. A
missing count prints `not measured`.

### 3.13 The board dashboard

`harness dashboard build-db` reads the work tree and writes `.harness/board.sqlite`.
The database is a cache. The tree stays the truth. The schema comments say so.
`harness dashboard serve` serves the kanban from the cache with `http.server` on port
8412 (`HARNESS_BOARD_PORT`). `harness dashboard static -o board.html` writes one
self-contained page. `infra/board/` runs the server in a container from
`python:3.11-slim` pinned by digest, and rebuilds the cache on a timer.

The page shows sprints, epics, the three states, `work` and `eye` per task, the human
verdict queue with its age, and the days that remain in each sprint.

### 3.14 Ports

| port | variable | service |
|---|---|---|
| 8410 | `HARNESS_RAG_PORT` | RAG MCP server |
| 8411 | `HARNESS_RAG_STATE_PORT` | RAG index state |
| 8412 | `HARNESS_BOARD_PORT` | board dashboard |

`harness ports` binds each port to test it. A taken port reports the port, the process
that holds it when `ss` or `lsof` exists, and the variable that overrides it.

### 3.15 The machine environment file

`harness env` writes `.harness/env.local`. It derives every value. It asks for nothing.

| variable | derived from |
|---|---|
| `HARNESS_REPO_ROOT` | `git rev-parse --show-toplevel` |
| `HARNESS_REPO_SLUG` | the root with `/` replaced by `-` |
| `HARNESS_CLAUDE_HOME` | `$CLAUDE_CONFIG_DIR` or `~/.claude` |
| `HARNESS_MEMORY_DIR` | `<claude home>/projects/<slug>/memory` |
| `HARNESS_PROJECT` | the basename of the root, lower case |
| `HARNESS_RAG_PORT`, `HARNESS_RAG_STATE_PORT`, `HARNESS_BOARD_PORT` | the environment, or the defaults |

## 4. Versions and upgrades

`harness/__init__.py` holds `VERSION`. The manifest records the version that installed
the files. `harness upgrade` rewrites every owned file that still matches its recorded
checksum, reports every owned file that the project edited, runs the migration steps
between the two versions, and records the new version. `harness uninstall` removes the
owned files that still match, keeps everything else, and lists what it kept.

## 5. What the harness does not do

- It does not estimate dates. A size is not a promise.
- It does not close a task with an eye. A person does.
- It does not set a target. A person does.
- It does not measure whether a task was the right task.
