---
id: TASK-0001
title: Start the harness in this repository
work: XS
eye: NONE
owner: user
---

# TASK-0001 — Start the harness in this repository

## Why

`init` created the board, the skills, and the rules. It measured nothing about
{{PROJECT}}. A profile with no answers writes generic skills, and a board with no sprint
computes nothing. This task holds the steps that turn the install into a working board.

The harness does not track this file. Move it, edit it, or remove it. `doctor` never
asks for it again.

## What to do

1. Run `python3 -m harness help`. It names what `init` created and what you own.
2. Run `python3 -m harness profile ask`. Answer the four questions in your words.
3. Run `python3 -m harness skills generate`. It writes the skills from your answers.
4. Run `python3 -m harness new sprint --title "..." --starts YYYY-MM-DD --ends YYYY-MM-DD`.
5. Run `python3 -m harness new epic --sprint sprint-001 --title "..."`.
6. Run `python3 -m harness assign TASK-0001 --epic EP-01`. The board needs an epic.
7. Run `python3 -m harness start TASK-0001`, then `python3 -m harness done TASK-0001`.
8. Open Claude Code in this repository. Accept the workspace trust dialog once.

## Done when

- `python3 -m harness doctor` exits 0.
- `python3 -m harness profile show` prints four answers that are not empty.
- `python3 -m harness check` exits 0 with at least one sprint.
- `python3 -m harness next` names a task that is not this one.

## Not covered

This task does not start the Docker stacks. The search index and the board page are
both optional. Run `python3 -m harness help rag` for the search index. Read
`infra/board/README.md` for the board page.
