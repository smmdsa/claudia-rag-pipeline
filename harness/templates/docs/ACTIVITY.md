# Front board — {{PROJECT}}

The live fronts of the team. One row per front. Humans write the rows.
`python3 -m harness session open` reads them and numbers them for the brief. The
numbers are per brief. Name a front by its text in a later session.

Relations:

- `docs/sessions/*.md` — history, one document per session, append only.
- `docs/session-log.md` — one row per session.
- `work/` — the committed work. The tree computes its state.
- this file — the fronts that are hot now, and who owns each one.

States: `active` · `paused` · `blocked` · `closed` (then move the row to the Archive).

## Fronts

| front | owner | state | touched | next step |
|---|---|---|---|---|
| (the front) | (who) | active | 2026-01-01 (commit or session) | (the next step) |

## Archive

| front | owner | state | touched | outcome |
|---|---|---|---|---|
