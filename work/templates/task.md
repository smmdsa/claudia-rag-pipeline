---
id: {{ID}}
title: {{TITLE}}
work: S
eye: NONE
owner: agent
---

# {{ID}} — {{TITLE}}

## Why

(the evidence: what was measured, with `file:line`)

## What to do

1. (step)

## Done when

- (a condition that a person or a checker can test, one per line)

## Not covered

(the axis that this task does not touch. This section is mandatory.)

## Notes

(the record of the work. `python3 -m harness note {{ID}} --text "..."` writes one line
here. The agent writes a note on every `start` and on every `done`. A note holds what
the agent measured, tried, and discarded. A note can hold the user's verdict with
`--by user`. The `## Verdict` section above stays the only place that closes a task.)
