---
id: sprint-000
title: Setup
starts: 2026-09-04
ends: 2026-09-18
---

# sprint-000 — Setup

## The one sentence

The harness runs on itself: installed, profiled, and measured.

## Where this scope comes from

`.harness/manifest.json` records `created_at` 2026-09-04T19:23:31-03:00. `init` ran
here on that date. On 2026-09-05 the user asked for the board of this repository:
"debemos debidamente asignarla a sprint epic etc, respetando nuestro sistema desde el
core". This sprint holds the setup that the install left open.

sprint-000 ships. Every later sprint stays local. `.gitignore` holds that rule. A
reader who opens this repository finds one worked sprint: this sheet, one epic sheet,
and one task in a state folder.

## Objectives, and how each one is checked

| # | objective | check |
|---|---|---|
| 1 | The install is sound | `python3 -m harness doctor` exits 0 |
| 2 | The project answers the four profile questions | `python3 -m harness profile show` prints four answers that are not empty |
| 3 | The tree holds a sprint and keeps its shape | `python3 -m harness check` exits 0 with at least one sprint |
| 4 | The board names work that is not the setup | `python3 -m harness next` names a task that is not TASK-0001 |

Objective 2 needs the user. `profile ask` reads four answers about this project, and
the agent writes none of them.

## Definition of done

- Every task with an eye has a verdict in the user's words.
- `python3 -m harness check` is green.

## What this sprint does NOT do

- It starts no Docker stack. The search index and the board page are both optional.
  `python3 -m harness help rag` holds those steps.
- It changes no adopter-facing feature. sprint-001 holds that work.
