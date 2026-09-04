# The search index stack

A local search index over this repository and the agent's durable memories. It runs
in Docker and it knows this project only. `session open` reports its health at step 0.

## Start

```bash
./infra/rag/up.sh          # CPU: portable, runs on any machine
./infra/rag/up.sh --gpu    # GPU: about 10 times faster at indexing; needs nvidia-container-toolkit
```

`up.sh` reads `.harness/env.local`. `python3 -m harness env` derives that file from
this machine. No path is written by hand. If the file is missing, `up.sh` derives it.
Before `up`, the script checks the two ports and stops if one is taken.

| command | what |
|---|---|
| `./infra/rag/up.sh down` | stop |
| `./infra/rag/up.sh logs -f rag-agent` | watch the indexing |
| `python3 -m harness rag health` | the canary: what the session sees now |
| `python3 -m harness rag update` | re-index now |
| `python3 -m harness rag config` | regenerate `config/index.yml` from the profile |

## The two services

| service | port (loopback only) | variable | role |
|---|---|---|---|
| `rag` | 8410 | `HARNESS_RAG_PORT` | the MCP server over HTTP. `.mcp.json` points here |
| `rag-agent` | 8411 | `HARNESS_RAG_STATE_PORT` | re-indexes every 15 min, serves `/state` |

## The mount is read only

The container cannot write into the repository. This is a file system guarantee,
not a convention. Prove it on your machine:

```bash
docker compose --env-file .harness/env.local -f infra/rag/docker-compose.yml exec rag touch /src/repo/.probe
# touch: cannot touch '/src/repo/.probe': Read-only file system
```

## Freshness: `synced` and `content` are two numbers

The canary prints two ages per collection, and only one is freshness:

```text
[ok ] repo-docs   551 docs  synced 28 s   content 4 d   /src/repo
```

- `synced` — when `qmd update` covered that collection last. This is freshness. It
  comes from the per-collection line that qmd prints: `Indexed: N new, N updated, N
  unchanged, N removed`.
- `content` — the mtime of the newest source file. It says when a person touched
  those files. It says nothing about the index.

A canary that reads the file date fails in both directions: it cries wolf over a
collection nobody edits, and it stays blind when the indexer dies. `qmd update` exits
0 even when it fails, so the exit code carries no signal. The `Indexed:` line does.

## Statuses

| status | meaning | what to do |
|---|---|---|
| `ok` | synced inside the limit | nothing |
| `sync-pending` | the agent just started | wait a minute |
| `needs-embed` | documents with no vector | the agent embeds them; watch the logs |
| `stale` | no `qmd update` inside 3 intervals | read `logs -f rag-agent` |
| `never-synced` | not covered since the agent started | the config or the mount is wrong |
| `path-missing` | the container path does not exist | check the volumes in the compose file |
| `orphan-in-index` | indexed, not declared | remove it, or declare it |

## What the image contains

`@tobilu/qmd` from `bun.lock`, installed with `--ignore-scripts`, on `oven/bun`
pinned by digest, plus `python3` from the distribution for the agent. Nothing else.
