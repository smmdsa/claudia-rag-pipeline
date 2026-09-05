---
id: EP-01
title: The harness runs on itself
sprint: sprint-000
work: M
eye: GLANCE
---

# EP-01 — The harness runs on itself

## Goal

This repository uses the harness that it ships, so that every rule meets the tool that
enforces it.

## The measurement this epic stands on

On 2026-09-05 this repository shipped the harness and did not run it:

- `python3 -m harness profile show` printed four empty fields. The generated skills
  read the profile, so they described no project.
- `python3 -m harness board` printed no sprint. Two tasks sat in the backlog, and
  `start` refuses a backlog task.
- `.harness/journal.jsonl` held 0 bytes. No session was ever closed here.

The rules were written and never measured against a running board.

## Technical sheet

| component | file | what changes |
|---|---|---|
| profile | `.harness/manifest.json` | four answers about this project. The user writes them |
| board | `work/sprints/sprint-000/` | the setup sprint. It ships |
| git | `.gitignore` | sprint-000 is the exception that ships. Every later sprint stays local |

## Board

`python3 -m harness board`. This sheet holds no progress. The tree computes it.

## Verdicts

(the tool appends a line here when a task with an eye closes)

## Out of scope

This epic changes no code under `harness/`. It runs the tool and records what the tool
measures. A defect that this epic finds becomes its own task in sprint-001.
