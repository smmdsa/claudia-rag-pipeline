# harness-rag-pipeline — rules for the agent

The harness installed this file (version 0.2.0). The skills point at
it. The rules live here and in `work/README.md`. They live nowhere else.

## Writing rules — read first, apply always

These rules apply to every English artifact in this repository: documentation,
code comments, commit messages, error strings, log lines, and skill descriptions.
They do not apply to user-facing marketing copy.

Write in ASD-STE100 Simplified Technical English.

1. Write one instruction per sentence. Use a maximum of 20 words.
2. Limit descriptive sentences to 25 words. Limit paragraphs to 6 sentences.
3. Use active voice. Name the actor.
4. Use simple tenses only. Do not use the present perfect.
5. Do not use "-ing" verb forms as connectors. Start a new sentence instead.
6. Use one word for one meaning across the whole repository. The Glossary holds the
   decisions. If a term is not in the Glossary, pick the shortest common option and
   add it.
7. Do not use should, would, may, might, or could. Use can, will, or must.
8. Write the condition before the command. Write "If the build fails, run X."
9. Keep articles and the word "that". STE is short. STE is not terse.
10. Delete these words on sight: leverage, seamlessly, robust, crucial, simply,
    powerful, comprehensive, delve, ensure that, in order to, it is important to
    note, it should be noted.
11. Write error messages in this order: what happened, why, what to do next.
12. State facts with numbers and names. Do not hedge.

Before you save a file, check your output against rules 1 to 12.

## Glossary — one word, one meaning

Use the left column. Never use the right column.

| Use | Never use |
|---|---|
| check | verify, validate, confirm, ensure |
| run | execute, invoke, trigger, kick off |
| get | fetch, retrieve, load, pull |
| set | configure, define, assign |
| remove | delete, drop, purge, clean up |
| start | launch, boot, spin up, initialize |
| update | modify, change, edit, revise |
| fix | repair, resolve, address |
| error | failure, fault, issue, problem |
| build | compile, assemble |
| sprint | iteration, cycle |
| epic | initiative, feature set |
| task | ticket, issue, story, card |
| board | dashboard, kanban |
| move | transition, promote, drag |
| work | effort, story points, complexity |
| eye | QA time, review time, human check |
| size | estimate, points |
| help | onboarding, tour, guide, walkthrough |
| note | comment, annotation, remark, log entry |
| modal | dialog, popup, lightbox, overlay |

Add a row when you choose a new term. Do not remove rows.

The word `build` means "to compile" and nothing else. The work system measures cost
with `work`, never with "build". The word `board` names the work board. The page that
`harness dashboard` serves is "the board page".

## Package policy

- The harness uses the Python standard library only. Add no third-party package to it.
- Do not add a dependency to this repository without a measured need and the user's
  approval, in the user's words.
- Install every dependency with install scripts disabled. Pin every version. Pin every
  Docker base image by digest.
- Never run `npm`. If the repository uses Node, use `pnpm` with `--ignore-scripts`.

## The design laws

The harness follows twelve laws. `docs/DESIGN-LAWS.md` in the harness repository
records each one with the measured failure that produced it. The short form:

1. The folder tree is the truth. The board is computed, never stored.
2. A rule lives in exactly one place.
3. A path that still exists does not prove that the path is correct.
4. Ask what number moves if the system dies right now.
5. A command that exits 0 on error hides the error.
6. Never write the string `wsl ` inside an executable file.
7. A default value must never look like a measurement.
8. The agent declares nothing that the user must own.
9. A green test can guard a bug. Prove that each test turns red.
10. Two sizes, not one: `work` and `eye`.
11. Every port must be checked before use.
12. Read before you write.

## Command reference

```text
python3 -m harness help [board|eye|skills|rag]    the adopter's map
python3 -m harness init | doctor | upgrade | uninstall | adopt <f> | restore <f>
python3 -m harness profile show|set k=v|ask        python3 -m harness skills generate
python3 -m harness board | next | list | show <id> | check | clock
python3 -m harness start <id> | done <id> [--verdict "..." --by user] | back <id>
python3 -m harness new task|epic|sprint --title ... [--id sprint-NNN]
python3 -m harness assign <id> --epic EP-NN | <epic folder name>
python3 -m harness priority <id> --by user --why "..." | --clear
python3 -m harness ceremony plan|triage|review|retro [--sprint S] [--write]
python3 -m harness state | target show|set <stock> <n> --by user --why "..." | escalate ...
python3 -m harness session open|draft|close --slug S   python3 -m harness journal tail|observe
python3 -m harness ports | env | rag health|config|update|link
python3 -m harness stack status|start|stop|up [--stack rag|board] [--gpu]
python3 -m harness dashboard build-db|serve|static -o board.html
```

Every read command accepts `--json`. `check` and `doctor` exit 1 on an error.

## The boundary of agent authority

The agent can:

- read every file, run every read command, and run `check` at any time;
- create tasks with `new task`, move them with `start`, `back`, and `done` for
  `eye: NONE`;
- write the session document, the journal line, and the front board rows of its own
  work;
- append an observation to `.harness/escalations.md`.

The agent never:

- closes a task with `eye: GLANCE` or `eye: RUN` without the user's words in
  `--verdict`;
- sets a target in `.harness/targets.json`, or a `priority`, from its own opinion.
  `priority` is written by `harness priority --by user` only. A hand-written
  `priority` line is denied by the hook and rejected by `check`;
- writes a verdict, a decision, or a date that the user did not give;
- moves a file under `work/` by hand;
- edits `.harness/manifest.json` or `.harness/journal.jsonl` by hand;
- commits or pushes without the user's request.

When a question sits above this boundary, the agent runs `python3 -m harness
escalate` and stops.

## The session pipeline

Open every session with the `session-start` skill. Close every session with the
`session-close` skill. Both skills run when no search index exists. They print a
warning and continue.
