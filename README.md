# harness-rag-pipeline

A portable harness for any repository. Copy one directory, run one command, and the
repository gets an agent pipeline and a SCRUM-shaped work board. Both live in git,
next to the code.

- **Python 3.10 or later, standard library only.** No third-party package. The two
  Docker images carry the only third-party code, pinned by lockfile and digest.
- **The folder tree is the truth.** The board is computed on every run and stored
  nowhere.
- **Two sizes per task:** `work` (agent cost) and `eye` (human verdict cost). A task
  with an eye does not close without the user's words.
- **Targets belong to the user.** The tool computes current values and reports the
  gap.

`ARCHITECTURE.md` names every component, port, and contract. `docs/DESIGN-LAWS.md`
records the twelve laws and the measured failures behind them. `docs/PROPOSALS.md`
lists what this product changes against its two sources.

## Install in 60 seconds

```bash
git clone git@github.com:smmdsa/claudia-rag-pipeline.git /tmp/hrp
cp -r /tmp/hrp/harness  /path/to/your/repo/harness
cd /path/to/your/repo
python3 -m harness init          # creates every missing file; never overwrites
python3 -m harness profile ask   # four questions: architecture, languages, purpose, end user
python3 -m harness skills generate
python3 -m harness doctor        # exit 0 sound · 1 damaged · 2 not initialised
```

`init` is idempotent. Run it twice and the second run creates nothing. If the
repository already has a `CLAUDE.md`, the rules go to `.claude/rules/harness.md` and
Claude Code loads both. If it has a `.claude/settings.json`, `init` merges the hooks
and keeps every other key.

Open Claude Code in the repository and accept the workspace trust dialog once. The
`SessionStart` hook then runs `doctor` on every session.

## The daily loop

```bash
python3 -m harness session open        # the brief: doctor, RAG canary, elapsed time, fronts, board, next
python3 -m harness next                # the first task the agent can start
python3 -m harness start TASK-0004
python3 -m harness done  TASK-0004 --verdict "it works on my screen" --by user
python3 -m harness session draft       # the skeleton of the session document
python3 -m harness session close --slug 2026-09-04-2011 --qa-closed TASK-0004=ok:run
```

The skills `session-start` and `session-close` drive these commands from Claude
Code. Both run when no search index exists. They print a warning and continue.

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

`work/README.md` holds the rules of the board. `check` measures the shape of the
tree and exits 1 on an error. It never measures whether a task is correct.

## The search index (Docker, optional)

```bash
python3 -m harness env           # derives .harness/env.local from this machine. Git ignores it.
python3 -m harness ports         # 8410, 8411, 8412 must be free, or override them
./infra/rag/up.sh                # CPU by default; --gpu for CUDA
python3 -m harness rag health    # RAG: OK · warnings · BROKEN, exit 0 · 1 · 2
```

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

The page reads a SQLite cache that `dashboard build-db` writes from the tree. The
cache is never the truth. The page shows when the cache was built.

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

The suite needs no network and no Docker. Every test module header records the
mutation that proved its tests turn red. `docs/MUTATION.md` holds the full record.

## Upgrade and uninstall

```bash
python3 -m harness upgrade          # rewrites the unchanged owned files, keeps your edits, records the version
python3 -m harness uninstall        # prints the plan
python3 -m harness uninstall --yes  # removes the owned files that still match; keeps the rest
```

## This repository hosts itself

`harness init` ran here. `python3 -m harness doctor` measures this repository too.
