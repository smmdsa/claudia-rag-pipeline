---
name: project-user-impact
description: States what the end user loses when a change fails. Use before a task with eye RUN or GLANCE closes, and in every review.
---

# Project user impact

Purpose: **install an agent pipeline and a folder board into any repository**. End user: **a developer who drives Claude Code in a repository and loses the record of what was done and checked when it fails**.

1. Run the `end-user-impact` skill with the task id.
2. Write one sentence: what the user cannot do if this change is wrong.
3. Name the check that a person must run to see the change. A green build is not a working feature.
4. Put that sentence in the task file under `## Done when`.
