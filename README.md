# harness-rag-pipeline

A portable harness for any repository. Copy one directory, run one command, and the
repository gets an agent pipeline and a SCRUM-shaped work board. Both live in git,
next to the code.

- **The folder tree is the truth.** The board is computed on every run and stored
  nowhere.
- **Two sizes per task:** `work` (agent cost) and `eye` (human verdict cost). A task
  with an eye does not close without the user's words.
- **Targets belong to the user.** The tool computes current values and reports the gap.
- **Standard library only.** No third-party package. The two Docker images carry the
  only third-party code, pinned by lockfile and digest. We run the harness on Python
  3.10 and on Python 3.14.

## Thanks to the contributors

These people wrote the code of this repository. Every merged patch adds a name.

<!-- contributors:start -->
<table>
  <tr><td align="center"><a href="https://github.com/smmdsa"><img src="https://avatars.githubusercontent.com/u/76018666?v=4&s=96" width="96" alt=""><br><sub><b>smmdsa</b></sub></a></td><td align="center"><a href="https://github.com/AldereteRuben"><img src="https://avatars.githubusercontent.com/u/58454065?v=4&s=96" width="96" alt=""><br><sub><b>AldereteRuben</b></sub></a></td></tr>
</table>
<!-- contributors:end -->

`scripts/contributors.py` writes that list from the GitHub API. A person runs it
once a week and reads the diff before the commit. No workflow writes to this
repository. The list holds names and pictures, and no commit counts, so it changes
when a new person lands a first patch.

`ARCHITECTURE.md` names every component, port, and contract. `docs/DESIGN-LAWS.md`
records the twelve laws and the measured failures behind them. `docs/PROPOSALS.md`
lists what this product changes against its two sources. `CHANGELOG.md` records every
version, with the measurement behind each change.

## How you use it

**You talk to your coding agent. The agent runs the harness.**

You build your software in a conversation. You do not type `python3 -m harness` to do
your work. You say what you want, or you type a slash command in your agent CLI, and
the agent runs the harness and reads the result back to you.

| you type or say | the agent runs |
|---|---|
| `/session-start` | the doctor, the RAG canary, the MCP link, the clock, the board, the state, and one brief |
| "what is next?" | `next`, and it names the first task it can start |
| "start the login task" | `start TASK-0004`, then it writes the code |
| "that works, close it" | `done TASK-0004 --verdict "<your words>" --by user` |
| "how is the sprint?" | `board`, `clock`, and `state` |
| `/session-close` | the session document, the journal line, the front board, the moves |

The rest of this README is the command reference. The agent reads it. You read it when
you want the raw output yourself, or when you set the machine up.

**Which agent?** We check this harness with Claude Code. The harness is plain files: a
rules file, markdown skills, and a CLI that speaks JSON with `--json`. Another agent
CLI reads the same files. We do not test the others, and we promise nothing about them.
Try yours, and tell us what breaks.

## Install

You run this once, by hand. After it, you talk to your agent.

```bash
git clone git@github.com:smmdsa/claudia-rag-pipeline.git /tmp/hrp
cp -r /tmp/hrp/harness  /path/to/your/repo/harness
cd /path/to/your/repo
python3 -m harness init          # creates every missing file; never overwrites
python3 -m harness help          # what init created, what you own, where the rules live
python3 -m harness profile ask   # four questions: architecture, languages, purpose, end user
python3 -m harness skills generate
python3 -m harness doctor        # exit 0 sound · 1 damaged · 2 not initialised
```

`profile ask` asks you four questions at the keyboard. It is yours, and not the
agent's: the four answers shape every skill that `skills generate` writes.

`init` also writes your first task to `work/backlog/`. It holds the setup steps, and
the manifest never records it: you move it across the board like any other task, and
`doctor` never asks for it again. `init` writes it once. It never writes it again after
the board holds a task.

`init` is idempotent. Run it twice and the second run creates nothing. If the
repository already has a `CLAUDE.md`, the rules go to `.claude/rules/harness.md` and
Claude Code loads both. If it has a `.claude/settings.json`, `init` merges the hooks
and keeps every other key.

Open your agent CLI in the repository. With Claude Code, accept the workspace trust
dialog once. The `SessionStart` hook then runs `doctor` on every session.

## The map

`python3 -m harness help` is the map. Four topics go deeper:

```bash
python3 -m harness help board    # the states, the daily commands, what check does not do
python3 -m harness help eye      # the second size, and why `done` refuses without --verdict
python3 -m harness help skills   # every skill under .claude/skills/, read from the tree
python3 -m harness help rag      # the optional search index and its three ports
```

## The daily loop

The `session-start` and `session-close` skills drive these. Both run when no search
index exists. They print a warning and continue.

```bash
python3 -m harness session open        # the brief: doctor, RAG canary, MCP link, fronts, board, next
python3 -m harness next                # the first task the agent can start
python3 -m harness start TASK-0004
python3 -m harness done  TASK-0004 --verdict "it works on my screen" --by user
python3 -m harness session draft       # the skeleton of the session document
python3 -m harness session close --slug 2026-09-04-2011 --qa-closed TASK-0004=ok:run
```

The `--verdict` carries YOUR words. The agent cannot write them, and `done` refuses a
task with an eye until it has them.

## The work board

```bash
python3 -m harness new sprint --title "Ship the login" --starts 2026-09-08 --ends 2026-09-19
python3 -m harness new epic   --sprint sprint-001 --title "The form"
python3 -m harness new task   --epic EP-01 --title "Add the password field" --work S --eye GLANCE
python3 -m harness board | next | list | show | check | clock
python3 -m harness ceremony plan|triage|review|retro --write
python3 -m harness state
python3 -m harness target set eye_queue 5 --by user --why "one person checks the work"
```

`work/README.md` holds the rules of the board. `check` measures the shape of the tree
and exits 1 on an error. It never measures whether a task is correct. Every read
command takes `--json`.

## The search index (Docker, optional)

```bash
python3 -m harness env           # derives .harness/env.local from this machine. Git ignores it.
python3 -m harness ports         # 8410, 8411, 8412 must be free, or override them
./infra/rag/up.sh                # CPU by default; --gpu for CUDA
python3 -m harness rag health    # RAG: OK · warnings · BROKEN, exit 0 · 1 · 2
python3 -m harness rag link      # did the index start after this agent? exit 1 when it did
```

`session open` repairs this stack for you. The canary is the signal and docker is the
repair: a green canary costs no docker call, and a BROKEN canary makes the session
start every container that exists and is stopped.

**Start the containers before you start your agent.** An agent CLI opens its MCP
connections once, when its process starts, and it never retries. A container that
starts later answers on its port and stays invisible for the whole session.
`rag link` measures that, and `session open` prints one line when the link is dead.

```bash
python3 -m harness stack status              # one line per service
python3 -m harness stack start | stop        # start what exists. Never build.
python3 -m harness stack up [--gpu]          # build the image, then start
python3 -m harness stack status --stack board
python3 -m harness session open --no-stack   # never touch docker
```

`start` never builds an image. A build needs the network and minutes, and a session
brief must stay fast. If no container exists, the brief names `stack up` and stops.
If docker is not on the PATH, or the daemon does not answer, the brief says so in one
line and the session continues without the index.

The stack mounts the repository read only. Prove it:

```bash
docker compose --env-file .harness/env.local -f infra/rag/docker-compose.yml exec rag touch /src/repo/.probe
# touch: cannot touch '/src/repo/.probe': Read-only file system
```

`infra/rag/README.md` explains the two services, the ports, and the statuses.

## The board page

```bash
python3 -m harness dashboard static -o board.html   # one file, no server
python3 -m harness dashboard serve                  # http://127.0.0.1:8412/
docker compose --env-file .harness/env.local -f infra/board/docker-compose.yml up -d --build
```

The page reads a SQLite cache that `dashboard build-db` writes from the tree. The cache
is never the truth. The server hashes every task path before it answers, and it
rebuilds the cache when the tree changed. You move a task, you reload, and you read the
new state. The page shows when the cache was built.

## Ports

| port | variable | service |
|---|---|---|
| 8410 | `HARNESS_RAG_PORT` | RAG MCP server |
| 8411 | `HARNESS_RAG_STATE_PORT` | RAG index state |
| 8412 | `HARNESS_BOARD_PORT` | board page |

## Tests

```bash
python3 -m unittest discover -s tests -v
```

The suite needs no network and no Docker. Every test module header records the mutation
that proved its tests turn red. `docs/MUTATION.md` holds the full record.

## Upgrade and uninstall

`CHANGELOG.md` holds the upgrade notes of every version. Read the notes of your target
version before you upgrade.

```bash
python3 -m harness upgrade          # rewrites the unchanged owned files, keeps your edits, records the version
python3 -m harness uninstall        # prints the plan
python3 -m harness uninstall --yes  # removes the owned files that still match; keeps the rest
```

## This repository hosts itself, and keeps its own board out of git

`harness init` ran here. `python3 -m harness doctor` measures this repository too.

This repository is the harness. The work that we do WITH the harness is not the
harness. So git tracks the tool and never the dogfood. `.gitignore` holds the list:
the sprints, the tasks, the roadmap, the session documents, the session log, the front
board, the journal, the escalations, and the targets. A pull request carries the tool
and nothing else.

`.harness/manifest.json` stays in git. It carries the checksums that prove that this
repository still hosts itself, and `doctor` reads them.

Every ignored file is a `seeded` file. `init` writes each one again from its template,
and `session open` does it for you:

```bash
git clone git@github.com:smmdsa/claudia-rag-pipeline.git && cd claudia-rag-pipeline
python3 -m harness session open   # RESEED: init wrote the missing seeded files again
python3 -m harness doctor         # exit 0
```

`session open` writes those files again only when EVERY problem that `doctor` reports
is a missing seeded file. An owned file with a wrong checksum, a manifest from another
version, or a missing hook stops the session and prints the fix. `init` never
overwrites a file, so the reseed never touches your work (law 12).

**This split belongs to this repository alone.** `harness/templates/gitignore.lines`
does not carry it. An adopter keeps the board in git, next to the code, because that
is the design: a task moves with `git mv`, and the history shows which commit moved it.
