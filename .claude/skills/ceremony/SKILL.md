---
name: ceremony
description: Runs a sprint ceremony from measured data: plan, triage, review, or retro. Produces a document with an agenda and open questions, and leaves the answers to the user. Use when the user says "plan the sprint", "triage the backlog", "review the sprint", "retro", or when a sprint passed its end date.
---

# Ceremony

The rules live in `work/README.md`. A ceremony never invents a verdict. It prepares
the questions and the user answers them.

```bash
python3 -m harness ceremony plan   [--sprint sprint-002] --write
python3 -m harness ceremony triage --write
python3 -m harness ceremony review [--sprint sprint-001] --write
python3 -m harness ceremony retro  [--sprint sprint-001] --write
```

`--write` puts the document under `work/sprints/<sprint>/ceremonies/<date>-<name>.md`.

## How to run one

1. Run the command. Read the document. Every number in it was computed now.
2. Print the "Questions for the user" section and stop.
3. Write the user's answers under the questions, in the user's words, with the date.
4. Apply the answers with the board commands: `assign`, `new task`, `done --verdict`,
   `target set --by user`. Never by hand.
5. Run `python3 -m harness check`.

## The four ceremonies

| ceremony | reads | the user decides |
|---|---|---|
| plan | the backlog, the roadmap, the targets | what enters, in which epic, and what is first |
| triage | the backlog and the git age of each file | what stays, what splits, what is removed |
| review | the sprint tree and the clock | the verdict of each eye task, and what carries over |
| retro | the journal inside the sprint dates | which surprise becomes a rule, which target is wrong |

## An overdue sprint

When the clock reports a sprint past its end with open tasks, run `review`. The
command does not move the date. The user decides: close the sprint, carry the tasks
to the next one with `assign`, or remove them.
