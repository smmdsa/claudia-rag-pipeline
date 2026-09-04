---
name: architecture-reader
description: Reads the architecture of the project from the profile and the code before a change. Names the components, the boundaries, and the contracts that the change crosses. Use when a task touches more than one component, when the agent must say where a piece of logic lives, or when a plan names a component that nobody measured.
---

# Architecture reader

## Step 1 — the declared architecture

```bash
python3 -m harness profile show
```

The profile is what the user declared. If the code disagrees with it, report the
disagreement. Do not edit the profile.

## Step 2 — the measured architecture

For the component that the task names:

1. Find its entry points. List them with `file:line`.
2. Count the call sites of each entry point. Use the `research` skill when the count
   matters. A grep counts one form; an event can travel as a symbol, as a literal
   string, and as a DOM event.
3. Name every boundary that the change crosses: a process, a container, a network
   port, a database, a file format, a queue.
4. For each boundary, name the contract: the schema, the port, the environment
   variable, the file path.

## Step 3 — the report

```text
Component: <name>
Declared: <one line from the profile>
Entry points: <file:line, ...>
Call sites: <count per entry point, and which form was counted>
Boundaries crossed: <list with the contract of each one>
Disagreements with the profile: <none | list>
What this read did not measure: <list>
```

The last line is mandatory. A read that hides its blind spots reads as complete.
