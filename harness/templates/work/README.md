# The work board

> **The folder tree is the truth. The board is computed, never stored.**
>
> A task file lives in exactly one state folder, and that folder IS its state. No
> file stores a status, a percentage, or a count. Run the tool and it computes the
> board from the tree:
>
> ```bash
> python3 -m harness board      # the whole picture
> python3 -m harness next       # the first task the agent can start now
> python3 -m harness check      # measure the shape of the tree; exit 1 on any error
> ```
>
> Never write progress into a markdown file. A stored number rots in silence, and
> then a reader treats it as a measurement. The source project measured that
> failure four times.

## Why a folder and not a tracker tool

The state of the work lives next to the work, in git. A task moves with `git mv`, so
the history shows when it moved and which commit moved it. A review of a task is a
diff. No account, no sync, no second list.

## The layout

```text
work/
├── README.md                          this file — the rules
├── ROADMAP.md                         the long horizon. The user writes it.
├── backlog/TASK-NNNN-slug.md          tasks that belong to no sprint
├── templates/{task,epic,sprint}.md    the molds that `new` uses
└── sprints/sprint-NNN/
    ├── sprint-NNN.md                  starts, ends, goal, done rule
    ├── ceremonies/                    plan, triage, review, retro documents
    └── epic-NN-slug/
        ├── epic-NN-slug.md            goal, technical sheet, verdicts
        ├── todo/                      TASK-NNNN-slug.md
        ├── in-progress/
        └── done/
```

Ids are global and sequential: `TASK-0001`, `TASK-0002`. The folder gives the epic.
The id carries no epic, because the folder is the truth and the id is a label.

## The two sizes, and why there are two

Every task carries two sizes. One measures the agent's cost. The other measures the
user's.

| `work` | meaning |
|---|---|
| `XS` | minutes. One line, one string, one constant |
| `S` | under an hour. One function, one field, one document |
| `M` | a session. Several files, or a new panel |
| `L` | more than a session. A new system, or a design that does not exist yet |
| `XL` | split it. An XL task is a task that nobody scoped |

| `eye` | meaning |
|---|---|
| `NONE` | a checker or a compiler can close it. No human must look |
| `GLANCE` | one screenshot or one forced frame closes it |
| `RUN` | the user must run the software. Nothing else closes it |

The second axis exists because the measured bottleneck of an agent-driven project is
the eye of the user, not agent hours. The source project saw its verdict queue reach
11 items against a cap of 5, and 7 builds shipped without a human verdict. A board
that counts only effort lets an agent stack work that nobody can check. This one
cannot: `done` refuses an eye task without `--verdict`.

## Three more fields

| field | values | meaning |
|---|---|---|
| `owner` | `agent` (default) · `user` | WHO does the work. A task can need no eye and still be one that only the user can do |
| `due` | `YYYY-MM-DD` | the work has a deadline outside this repository. It outranks everything in `next` |
| `priority` | `1` · absent | the USER named this task as the next thing, in the user's words. It carries `priority-by`, `priority-date`, and `priority-why` |

`owner` and `eye` answer different questions. `eye` says who CLOSES a task. `owner`
says who DOES it. `next` reports `owner: user` tasks first, because the agent cannot
do them, and it never lets them go quiet.

`priority` is set from what the user SAID, and never from what the agent thinks
matters. A priority that the agent assigns turns `next` into an opinion. The tool
holds this rule: `python3 -m harness priority TASK-NNNN --by user --why "..."` is the
only writer, `check` exits 1 on a priority with no author or no date, and the
pre-write hook denies the hand edit. Source B measured the failure on 2026-09-04:
the board ranked by epic number and named the wrong epic, because that was the only
order the tool knew.

## The rules

1. **The folder is the state.** Move a task with the tool, never by hand. The hooks
   deny a hand move.
2. **One task, one file.** If a task needs two verdicts, it is two tasks.
3. **A task names what it does NOT cover.** Every task file ends with that section.
4. **A task cites evidence.** A line of code, a report, or a measurement.
5. **A task with `eye: RUN` or `eye: GLANCE` cannot close without a human verdict.**
   The tool writes the verdict, with the date, into the task file and the epic sheet.
6. **An epic sheet never tracks progress.** It holds the goal, the technical sheet,
   and the verdicts. Progress comes from the tree.
7. **Work in progress stays under the cap.** The cap is 3 until the user declares
   `wip` in `.harness/targets.json`. `check` warns above it.
8. **A sprint declares `starts` and `ends`.** The clock computes the days that remain.
   A sprint that passes its end with open tasks is overdue. No command moves a date.
9. **All content is English, in ASD-STE100 Simplified Technical English.**

## The state machine

```text
backlog ──assign──> todo ──start──> in-progress ──done──> done
                                         └──back──> todo
```

```bash
python3 -m harness assign TASK-0004 --epic EP-01
python3 -m harness start TASK-0004
python3 -m harness done  TASK-0004                              # eye NONE
python3 -m harness done  TASK-0004 --verdict "it works" --by user  # eye GLANCE or RUN
python3 -m harness back  TASK-0004
python3 -m harness priority TASK-0004 --by user --why "the words"   # or --clear
```

A task is READY when it sits in `todo`, every task in its `blocked-by` list is done,
and no `needs-decision` is open. `next` returns the first ready task and ranks by
`due`, then `priority`, then sprint, then epic, then id.

## The ceremonies

| command | when | what it writes |
|---|---|---|
| `ceremony plan` | before a sprint starts | candidates from the backlog with work and eye totals, and the questions |
| `ceremony triage` | any time the backlog grows | tasks with missing fields, old tasks, and the questions |
| `ceremony review` | at the end of a sprint | done, open, awaiting a verdict, overdue, and the questions |
| `ceremony retro` | after the review | what the journal recorded, and the questions |

A ceremony never invents a verdict. It prepares the questions. The user answers them.

## What this system does not do

- It does not estimate dates. A size is not a promise.
- It does not measure whether a task was the right task.
- It does not close a task. `check` reads the SHAPE of the tree. A person closes a task.
