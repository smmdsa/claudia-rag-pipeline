# The hooks

`.claude/settings.json` calls `python3 -m harness hook <name>` on five events. The
event names, the matchers, and the payload shapes come from the Claude Code hooks
reference (https://code.claude.com/docs/en/hooks), read on 2026-09-04.
`tests/test_hooks.py` feeds these payloads to each hook.

## Events and matchers

| event | matcher | hook | exit | output |
|---|---|---|---|---|
| `SessionStart` | `startup\|resume\|clear\|compact` | `session-start` | 0 | plain text on stdout, added to the context |
| `PreToolUse` | `Write\|Edit` | `pre-write` | 0 | JSON deny, or nothing |
| `PreToolUse` | `Bash` | `pre-bash` | 0 | JSON deny, or nothing |
| `PostToolUse` | `Write\|Edit\|Bash` | `post-work` | 0 or 2 | 2 with the check errors on stderr, fed back to Claude |
| `Stop` | (all) | `stop` | 0 | JSON `systemMessage`, or nothing |
| `SessionEnd` | (all) | `session-end` | 0 | one line per observation appended |

Project hooks need the workspace trust dialog once. Claude Code asks for it.

## The payloads

Common fields: `session_id`, `hook_event_name`, `cwd`.

```json
{"hook_event_name": "PreToolUse", "tool_name": "Write",
 "tool_input": {"file_path": "work/sprints/sprint-001/epic-01-x/todo/TASK-0009-y.md", "content": "..."}}
{"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "mv work/sprints/a/b/todo/x.md work/sprints/a/b/done/"}}
{"hook_event_name": "PostToolUse", "tool_name": "Edit", "tool_input": {"file_path": "work/backlog/TASK-0003-z.md"}, "tool_result": "..."}
{"hook_event_name": "Stop", "stop_hook_active": false}
{"hook_event_name": "SessionEnd", "reason": "other"}
```

## The deny shape

```json
{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                        "permissionDecisionReason": "..."}}
```

## What each hook denies or reports

- `pre-write` denies: a NEW file inside a state folder (`todo/`, `in-progress/`,
  `done/`); any write to `.harness/manifest.json`, `.harness/journal.jsonl`,
  `.harness/board.sqlite`; any write to `.harness/targets.json`. An `Edit` of an
  existing task file passes: the agent writes the sections of a task.
- `pre-bash` denies `mv`, `cp`, `rm`, `rmdir`, `git mv`, and `git rm` on `work/`.
  It parses each shell segment. It denies `git commit --amend`, forced pushes, and
  push operations that remove a remote ref. Git flag order does not bypass this check.
- `post-work` runs `check` after a change under `work/`, or after any Bash command
  that names `work/` or the harness. Red returns exit 2 with the errors on stderr.
- `stop` reports the tasks that wait for a human verdict and the sprints past their
  end date. It never blocks the stop. It exits 0 at once when `stop_hook_active` is
  true.
- `session-end` appends one `observation` line to the journal per stock over its
  target, once per stock per day.

## Environment

The commands run `cd "$CLAUDE_PROJECT_DIR"` first. Claude Code sets that variable
to the project root. Every hook exits 0 on an unexpected payload, so a hook never
breaks a session.
