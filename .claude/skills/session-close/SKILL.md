---
name: session-close
description: Closes a work session. Writes the timestamped session document, updates the session index and the front board, moves the finished tasks with the tool, appends one line to the journal, asks the RAG stack to re-index, and updates the durable memory. Use at the end of every session, or when the user says "close", "done for today", "save progress".
---

# Session close

The rules live in `CLAUDE.md` (or `.claude/rules/harness.md`) and `work/README.md`.
This skill does not repeat them. Run the steps in order. Each one feeds the next.

## Step 1 — the board first

```bash
python3 -m harness board
python3 -m harness check
```

1. Move every task whose `Done when` is met. Read the section, test each line, and
   say which line you tested and how. `git mv` is not a check.
2. A task with `eye: GLANCE` or `eye: RUN` stays in `in-progress` until the user
   gives a verdict. When the user gave one, in their words:
   `python3 -m harness done TASK-NNNN --verdict "<the words>" --by user`.
   Never infer a verdict. Compiling green is not working.
3. A task that appeared in the session and has no file: create it now with
   `python3 -m harness new task`, with both sizes and its `Not covered` section.
   Work that appears and is not written down is lost.
4. `check` must be green before the close. It has an exit code. A rule in a comment
   does not.

## Step 2 — the draft

```bash
python3 -m harness session draft
```

It writes `docs/sessions/<slug>.md` with the measured fields filled: the timestamp,
the branch, the commits since the last close, and `git status`. Read it.

## Step 3 — the narrative

Do not mechanise this step. Write from the conversation:

1. **TL;DR** — one sentence, the most important thing.
2. **What happened** — bullets with a commit hash or a file each. If the work stayed
   uncommitted, say so.
3. **Decisions** — why X and not Y. What was discarded. Quote the user when the
   words decided.
4. **Repository state at close** — for each uncommitted file: which front it belongs
   to and why it is not committed. If it carries over from a past session, say since
   when.
5. **Open items** — with enough context that the next session does not guess.
6. **References** — files and documents.
7. **How to resume** — 3 to 5 concrete steps. Give the plan, not the judgement.

## Step 4 — the front board

Edit `docs/ACTIVITY.md`. Touch only the rows of the fronts that this session moved:
state, `touched` date with the commit or the slug, next step. A closed front moves
to the Archive in the same edit. Do not rewrite another person's rows.

## Step 5 — close

```bash
python3 -m harness session close --slug <slug> \
  --qa-closed TASK-NNNN=ok:run \
  --qa-open TASK-NNNN \
  --surprise "..." --failed "..."
```

The command checks the document, adds the row to `docs/session-log.md`, appends the
journal line, appends one observation per missed target, and asks the RAG stack to
re-index. If the stack is down, it says so and continues.

`--qa-closed` takes only what the user SAW. A verdict of "not ok" is a close too: the
item leaves the queue and becomes work. If the session closed no verdict, pass
nothing: the empty list is the data. Two empty closes in a row are a pattern.

## Step 6 — the memory

If the session produced a lesson that outlives one document, write it to the
durable memory directory that the system prompt names, and add its line to
`MEMORY.md`. If the session was tactical only, skip this step.

If this session changed the state of a front that has a memory, open that memory's
index line and its header, and make them tell the same story as the board.

## Step 7 — report

```text
Session closed.
- document: docs/sessions/<slug>.md
- index: docs/session-log.md
- front board: <fronts moved>
- journal: <n> verdict(s) closed, <n> observation(s)
- eye queue: <n> task(s) await a verdict
- RAG: re-index requested | not re-indexed (<reason>)
- memory: updated | no change
- repository: <n> file(s) not committed
```

The eye queue line prints always, even at 0. A close that reports production and
hides the queue is the close that let the queue go from 2 to 8 unseen.

## Notes

- Do not commit on your own. The user decides when.
- If the user is about to commit, offer to run this skill first, so the session
  document rides in the same commit.
- A session with no code change still gets a document with an honest TL;DR.
