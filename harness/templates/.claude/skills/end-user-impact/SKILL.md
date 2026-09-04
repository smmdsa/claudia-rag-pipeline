---
name: end-user-impact
description: States what the end user gains or loses from a change, in one sentence, and names the human check that shows it. Use before a task with eye GLANCE or RUN closes, in every sprint review, and when the agent must decide whether a task needs an eye.
---

# End-user impact

## Step 1 — who the user is

```bash
python3 -m harness profile show
```

The profile names the end user and what they lose when the software fails. If the
profile is empty, ask the user for the answer. Do not invent it.

## Step 2 — the sentence

Write one sentence: "If this change is wrong, the user cannot <verb> <object>."
If you cannot write it, the change has no user impact, and its `eye` is `NONE`.

## Step 3 — the check

Name the check that a person must run to see the change:

- `GLANCE`: one screenshot or one forced state shows it.
- `RUN`: the person must use the software along a path. Name the path.

Write the sentence and the check under `## Done when` in the task file.

## Step 4 — the verdict

A green build is not a working feature. The tool refuses `done` on an eye task
without the user's words. Ask the user to run the check and say what they saw. Pass
their words verbatim.
