---
id: TASK-0001
title: Initialise the harness in this repository
work: XS
eye: NONE
owner: user
---

# TASK-0001 — Initialise the harness in this repository

## Why

This repository holds the harness and no work yet. A board with no sprint computes nothing, and a
harness with no profile writes generic skills. The first task of any adopter is the same: install,
check, profile, and open the first sprint. This task holds those steps so that a clone reads them
as its first instruction.

## What to do

1. Run `python3 -m harness init`. It creates every missing file and never overwrites one.
2. Run `python3 -m harness doctor`. It must exit 0. If it exits 1, it names the file and the fix.
3. Run `python3 -m harness profile ask`. Answer the four questions in your words.
4. Run `python3 -m harness skills generate` and `python3 -m harness rag config`.
5. Run `python3 -m harness new sprint --title "..." --starts YYYY-MM-DD --ends YYYY-MM-DD`.
6. Run `python3 -m harness new epic --sprint sprint-001 --title "..."`, then `new task --epic EP-01`.
7. Run `python3 -m harness assign TASK-0001 --epic EP-01`, `start TASK-0001`, and `done TASK-0001`.
8. Open Claude Code in the repository and accept the workspace trust dialog once, so the hooks run.

## Done when

- `python3 -m harness doctor` exits 0.
- `python3 -m harness profile show` prints four non-empty answers.
- `python3 -m harness check` exits 0 with at least one sprint.
- `python3 -m harness next` names a task that is not this one.

## Not covered

This task does not start the Docker stacks. `infra/rag/README.md` and `infra/board/README.md` hold
those steps, and both stacks are optional.
