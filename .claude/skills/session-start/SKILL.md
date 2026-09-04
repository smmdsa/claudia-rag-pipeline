---
name: session-start
description: Opens a work session. Runs the harness doctor and the RAG canary first, computes the elapsed time since the last session, compares the repository against the recorded close, reads the front board and the work board, and prints one brief. Use at the start of every session, or when the user says "start", "let's begin", "resume".
---

# Session start

The rules live in `CLAUDE.md` (or `.claude/rules/harness.md`) and `work/README.md`.
This skill does not repeat them. It runs the tool and reads the result.

## Step 0 — the canary runs first

```bash
python3 -m harness session open
```

The command runs `doctor` at step 0. If the repository is not initialised, it runs
`init` and prints what it created. Then it runs the RAG canary, the clock, the
board, and the state. It prints one brief. Add `--json` for the raw data.

What each line of the brief means:

- `HARNESS: damaged` — fix it before any work. The line names the file and the fix.
- `RAG: BROKEN` — this session searches blind. Say so in the first line of your brief.
  Every claim about call sites then comes from grep, and grep misses the literal
  string form and the DOM form of an event. Do not fix the RAG on your own. Report it.
- `RAG: warnings` — one line in the brief.
- `RAG: OK` — do not mention it. A canary that sings always is not read.
- `STALE` on the last session — the claims of that document are premises to check,
  not facts.
- `CHECK RED` — fix the tree before new work. Working on a broken tree is starting
  in debt.

## Step 1 — read the last session document

The brief names it. Read it. Take: the TL;DR, the open items, and "How to resume".
The open items are a menu for the user, not a to-do list for the agent.

## Step 2 — the fronts

The brief numbers the rows of `docs/ACTIVITY.md` in print order. **The numbers are
per brief.** If the user names a number from a past session, print the table again
or ask for the front by its text. A row with a `touched` date over 14 days old is a
row to re-check, not to trust.

When the RAG canary is green, ask the index about each front you print:

```bash
curl -s -X POST http://127.0.0.1:${HARNESS_RAG_PORT:-8410}/mcp   # through the MCP tools of qmd
```

Use the `mcp__qmd__*` tools with the collection `repo-docs` for what the team did,
and `memory` for why a rule exists. Do this for the fronts you print, not for all of
them. When the canary is not green, skip this. A dead index answers in silence.

## Step 3 — the brief to the user

Print, in this order:

1. The RAG line, only when it is not `OK`.
2. Last session: slug, closed how long ago, TL;DR.
3. Repository: branch, commits since the close, files not committed. Name the files
   that the last close already declared as work in flight, apart from the new ones.
4. The fronts table with `#` numbers, and the sentence "Numbers are per brief".
5. The board: in progress, awaiting a verdict, `NEXT`, and the decisions that block.
6. Targets missed, with who set each target.
7. One suggestion. It comes from `NEXT`, or from the decision that blocks it. If the
   eye queue is over its target, the suggestion is to drain it, not to build.

## Step 4 — wait

Do not start work. The suggestion can differ from what the user wants today. Wait
for the user to confirm or redirect.

## Degraded modes

- No RAG stack: the brief prints `RAG: BROKEN`. Continue.
- No `.harness/journal.jsonl` line yet: the brief says "first session". Continue.
- No git: the brief says so. Moves fall back to a rename. Continue.
