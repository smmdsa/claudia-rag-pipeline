---
name: board
description: Operates the folder board under work/. Lists tasks, shows one task, names the next one, moves a task between todo, in-progress, and done, creates sprints, epics, and tasks, and checks the tree. Use when the user says "list the tasks", "what is next", "start TASK-NNNN", "close the task", "how is the sprint", "new epic", "new task".
---

# Board

The rules live in `work/README.md`. This skill does not repeat them. The truth is
the folder tree. The board is computed on every run and stored nowhere.

## The instrument

```bash
python3 -m harness board                   # the whole picture
python3 -m harness next                    # the first task the agent can start now
python3 -m harness list --epic EP-02       # one line per task · --sprint · --state · --owner
python3 -m harness show TASK-0004          # the whole task file
python3 -m harness start TASK-0004         # todo -> in-progress (git mv)
python3 -m harness done  TASK-0004         # in-progress -> done (git mv). Eye tasks need --verdict.
python3 -m harness back  TASK-0004         # in-progress -> todo
python3 -m harness assign TASK-0004 --epic EP-02
python3 -m harness check                   # the shape of the tree; exit 1 on red
python3 -m harness clock                   # the days that remain
python3 -m harness new task|epic|sprint --title "..."
```

Every read command accepts `--json`.

## What to do with each request

| the user says | do |
|---|---|
| "what is next" | `next`. If nothing is ready, the command names the decision that blocks. Tell the user. Do not choose for them. |
| "list", "board", "how is it going" | `board`, or `list` with a filter when the user named an epic |
| "show TASK-NNNN" | `show`, then read the whole file before you speak |
| "start TASK-NNNN" | `start`, then read the file, then work |
| "close", "I finished" | read the rule below before `done` |
| "new task / epic / sprint" | `new`, then write the sections, then `check` |

## The rules this skill enforces

1. **`done` does not run before the `Done when` of the file is met.** Read the
   section, test each line, and say which line you tested and how.
2. **A task with `eye: RUN` or `eye: GLANCE` is closed by a human verdict.** The tool
   refuses `done` without `--verdict`. Pass the user's words verbatim with
   `--by user`. Never write words the user did not say.
3. **A task with `needs-decision` does not start.** If the user asks anyway, name the
   decision and what changes with each answer.
4. **A task with `owner: user` is not done by the agent, and `next` reports it
   first.** The agent has no key to it. If it has a `due`, name it in every brief
   until it closes.
5. **After you create or move anything, run `check`.** The post-work hook runs it
   too. A red check is reported before any other work.
6. **`priority: 1` comes from the user's words.** Set it when the user names the
   next thing. Never set it from your own opinion.

## Out of scope

- This skill does not decide what enters a sprint. `ceremony plan` prepares the
  candidates, and the user picks.
- `check` measures the SHAPE of the tree. It never measures whether a task is
  correct, whether a size is honest, or whether a done task works.
