# The board page

A kanban view of `work/` for a human. Three ways to get it:

```bash
python3 -m harness dashboard static -o board.html     # one file, no server, no Docker
python3 -m harness dashboard serve                    # http://127.0.0.1:8412/ from this machine
docker compose --env-file .harness/env.local -f infra/board/docker-compose.yml up -d --build
```

`python3 -m harness ports` checks port 8412 first. Override it with
`HARNESS_BOARD_PORT=<port>`.

## The cache is not the truth

The page reads `.harness/board.sqlite` (`/data/board.sqlite` in the container).
`dashboard build-db` writes that database from the folder tree. The container
rebuilds it every 300 s. The page shows `built_at`, so a reader knows the age of
what they read. The tree under `work/` stays the truth. `POST /rebuild` rebuilds now.

## What the page shows

Sprints with the days that remain, epics, the three states, `work` and `eye` per
task, the human verdict queue with the days each task waited, the tasks only the
user can do, and the sprints past their end date with open tasks.
