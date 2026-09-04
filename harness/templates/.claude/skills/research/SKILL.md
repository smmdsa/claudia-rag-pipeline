---
name: research
description: Deep research of the codebase with a 3-layer harness before any non-trivial change: many small read-only agents gather file:line evidence, a few agents trace flows over that evidence, and one reviewer audits the plan. Use when the user says "research", "map how X works", "do not assume", "check the premises of the plan", or before a change that touches code you do not know.
---

# Research — trace, do not assume

You are the top layer. You decompose the question, delegate to the workflow,
consolidate the evidence, and write a plan that the evidence supports. You do not do
the search yourself.

## When

Before any non-trivial work on code that you do not know. Any claim about call
sites, who calls what, whether an event is wired, where a value is set, or whether a
branch is dead is checked with agents, not recalled from memory. If you resume an old
plan, check its premises with this harness before you touch anything.

## Procedure

### 1. Decompose

Turn the goal into:

- `antQuestions` (8 to 14): atomic questions with a narrow return contract. Each one
  asks for raw data: "who publishes and who subscribes to event Y? file:line and a
  snippet", "the definition and every caller of Z", "is this branch dead?".
- `beeTasks` (1 to 4): composite traces `{ key, prompt }`. Each one follows a full
  flow or measures an impact: "trace the selection from emitter to panel and find
  the race", "what breaks if A moves to B".

Scale to the problem. A small question: a few ants and no bee. A change that alters
behaviour: a full batch, 2 or 3 bees, and a second round on the gaps.

### 2. Run the workflow

```text
Workflow({ name: 'research', args: { question, antQuestions, beeTasks } })
```

If the name does not resolve, pass the path: `.claude/workflows/research.js`.
Optional args: `repoNote` (the return contract), `antModel`, `beeModel`,
`reviewer: false`.

When the RAG stack is up, the agents use the `mcp__qmd__*` tools first. Grep reads
one tree. The index reads the history too. When the stack is down, the agents say
so, and the search was narrower.

### 3. Consolidate

When `{ ants, bees, gaps, reviewer }` comes back:

- Cross the evidence. When a bee says the code contradicts an ant, the code wins.
  Read the `file:line` yourself when they conflict.
- Close the `gaps` that the bees left open. Those are the correctness blockers. Close
  them with your own reads or a second batch of ants. Do not leave them for later.
- Check the linchpins before you plan. A plan on a linchpin nobody checked is smoke.

### 4. Deliver

A plan with a failing test first, then the minimal change, then the test command of
the repository, then the human check when the change alters what the user sees.
Lead with the verdict and the corrected premises. Then the plan.

## The return contract of the agents

Ants and bees are read-only. They return evidence: `file:line` and a verbatim
snippet of 4 lines or fewer. They return no opinion. Give them narrow contracts so
that consolidation stays cheap. You write the plan, not they.
