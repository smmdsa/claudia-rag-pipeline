# Changelog

Every entry names what changed, why it changed, and the measurement behind it. The
version numbers follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

`python3 -m harness upgrade` moves an installed harness to a new version. It rewrites
every owned file that you did not edit, it keeps every file that you did edit, and it
records the new version in `.harness/manifest.json`. Run `python3 -m harness doctor`
after an upgrade. It exits 0 when the install is sound.

## 0.2.0 — 2026-09-05

The adopter reads a map on the first run, the session repairs its own stack, and a
verdict lands in the right file.

### Added

- **`python3 -m harness help [board|eye|skills|rag]`** — the adopter's map. It names
  what `init` created, what the user owns, what the agent does alone, and where each
  rule lives. It copies no rule (law 2). `help skills` reads `.claude/skills/*/SKILL.md`
  on every run, and `help board` and `help eye` read the values that `harness.board`
  declares, so no list rots (law 1). Before this change, `init` created 36 files and
  printed one line, and the README that explains the system stayed in the harness
  repository.
- **A first task in the box.** `init` writes
  `work/backlog/TASK-0001-start-the-harness-in-this-repository.md`. The manifest never
  records it, because the adopter moves it across the board and `doctor` asks for every
  file that the manifest records. `init` writes it once, and never again after the
  board holds a task.
- **`python3 -m harness stack status|start|stop|up|ports [--stack rag|board] [--gpu]`** —
  the Docker stacks. `session open` calls `start` when the RAG canary reports BROKEN, so
  a new work day starts the containers that exist and are stopped. A green canary makes
  no docker call at all.
- **`python3 -m harness new sprint --id sprint-NNN`** — a sprint id that the counter
  cannot reach. `next_sprint_dir` counts up from the highest sprint, so it never writes
  `sprint-000`. A repository that wants a sprint zero for its setup needs the name.
- **`session open` writes the missing seeded files again.** A repository can keep its
  own board out of git. A clone then lacks every seeded file, and `doctor` turns red on
  a state that one `init` fixes. The brief prints `RESEED` and continues.
- **`session open --no-stack`** never touches docker. **`--no-rag`** still skips the
  canary.

### Fixed

- **A verdict landed in the epic sheet of another sprint.** Every sprint numbers its
  epics from `EP-01`, so two sprints answer to the same id. `find_epic` walked the
  sprints in order and returned the first match, and `move` used it to pick the sheet
  that receives a verdict. A task closed in `sprint-001` wrote the user's words into
  the sheet of `sprint-000`. `check` stayed green: the shape of the tree was correct,
  and the words were in the wrong file. `find_epic` now takes a `sprint`, and without
  one it names every candidate and stops. The folder name always identifies one epic.
- **`init` rewrote `.claude/settings.json` when no key changed.** `json.dumps` expands
  a compact array, so a repository that holds `"enabledMcpjsonServers": ["qmd"]` on one
  line got a diff that nobody made. A fresh clone reported a dirty tree on its first
  command. The merge now compares the parsed data against a copy taken before it, and
  it writes only on a real change (law 12).
- **`infra/rag/up.sh` refused to run on a stack that was already up.** It ran
  `harness ports`, which binds a port to test it and cannot name the holder. The stack's
  own containers held the ports, and the script told the user to override a port that
  nothing else wanted. `harness stack ports --stack rag` reports three states: free,
  held by this stack, and held by another process. `up.sh` now refuses only the third.
  `docker compose up -d` on a running stack is a no operation again.
- **`harness help` named a path that `init` never creates.** It pointed at
  `docs/DESIGN-LAWS.md` and offered `init` as the fix. The twelve laws travel to the
  adopter in short form inside `CLAUDE.md`, and the full record stays in the harness
  repository. The harness repository holds that file, so the path existed there and the
  text looked correct (law 3).
- **`harness stack <unknown>` raised `KeyError`.** `status` read the stack table before
  it checked the name. The error now names the two stacks (writing rule 11).

### Changed

- `doctor` marks every missing file as `missing-owned` or `missing-seeded`.
  `manifest.only_missing_seeded` reports when `init` is the whole fix. The reseed fires
  only when EVERY problem is a missing seeded file: an owned file with a wrong checksum,
  a manifest from another version, or a missing hook stops the session and prints the
  fix.
- `init` and the first session with no journal both name `python3 -m harness help`.
- The glossary holds a new row: `help`. Never use onboarding, tour, guide, or
  walkthrough.
- `work/README.md` records that an epic id repeats across sprints, with the date and
  the measured failure.

### Tests

151 tests, 0 red. Mutations M18 to M39 each turned at least one test red.
`docs/MUTATION.md` holds the record, the baseline, and the count after each restore.

Three tests turned red for real, with no mutation: the path that `init` never creates,
the `KeyError` on an unknown stack, and the settings file that a reseed rewrote.

### Upgrade notes

Run `python3 -m harness upgrade`, then `python3 -m harness doctor`. The upgrade rewrites
25 owned files. It keeps every owned file that you edited and names it. Nothing under
`work/` moves, and no task changes.

If your board holds two sprints, `--epic EP-01` now stops instead of guessing. Pass the
folder name of the epic, for example
`python3 -m harness assign TASK-0007 --epic epic-01-the-login-form`.

## 0.1.0 — 2026-09-04

The first version. `python3 -m harness init` installs an agent pipeline and a folder
board into any repository, with the Python standard library only.

- The folder tree is the truth. The board is computed on every run and stored nowhere.
- Two sizes per task: `work` for the agent's cost, `eye` for the user's. A task with an
  eye does not close without the user's words in `--verdict`.
- The user owns every target and every priority. `harness priority` writes the author
  and the date, a hand-written `priority` line is denied by the hook, and `check` exits
  1 on a priority with no provenance.
- `doctor` checks a checksum for every owned file and the presence of every seeded file.
- Two optional Docker stacks: a search index that mounts the repository read only, and
  the board page.
- `docs/DESIGN-LAWS.md` records twelve laws and the measured failure behind each one.
