# Backlog

Tasks that belong to no sprint. Each one is a task file with the same front matter
as a sprint task. Create one with:

```bash
python3 -m harness new task --title "..." --work S --eye NONE
```

Move one into a sprint with `python3 -m harness assign TASK-NNNN --epic EP-NN`.
`ceremony plan` lists the candidates with their sizes. `ceremony triage` flags the
ones with missing fields or old dates.

This file holds no task. A task in a README is a second list, and two lists diverge.
