---
name: project-map
description: Reads the architecture of this project before a change. Use when a task touches more than one component, or when the agent must name where a piece of logic lives.
---

# Project map

The profile declares: **Python package + two Docker services (qmd index, board page)**. Languages: python, shell, javascript.

1. Run `python3 -m harness profile show`. If the architecture changed, tell the user. Do not edit the profile.
2. Run the `architecture-reader` skill with the component that the task names.
3. Name every file that the change touches, with `file:line`. Count the call sites. Do not read them from memory.
4. If a call site lives in a dependency, say so. A grep that returns nothing does not close the question.
