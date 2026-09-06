"""The hook entry points. `.claude/settings.json` calls `python3 -m harness hook <name>`.

Every hook reads the JSON payload on stdin. `docs/HOOKS.md` records the payload
shapes. A hook never breaks a session: an unexpected payload prints a line and exits 0.
A deny prints the documented JSON and exits 0. Feedback after a tool ran prints to
stderr and exits 2.
"""
import json
import os
import re
import shlex
import sys

from harness import board, manifest, scaffold, state
from harness.board import all_tasks, scan
from harness.clock import overdue
from harness.util import rel

STATE_FOLDER = re.compile(r"(^|/)work/sprints/[^/]+/epic-[^/]+/(todo|in-progress|done)/[^/]+$")
TOOL_OWNED = (".harness/manifest.json", ".harness/journal.jsonl", ".harness/board.sqlite")
USER_OWNED = (".harness/targets.json",)
TASK_FILE = re.compile(r"(^|/)work/.*TASK-\d{4}[^/]*\.md$")
PRIORITY_LINE = re.compile(r"^\s*priority(-[a-z]+)?\s*:.*$", re.M)
MOVE_ON_WORK = re.compile(r"(^|[\s;&|(])(mv|cp|rm|rmdir)\s[^;&|]*\bwork/(sprints|backlog)\b")
GIT_MV_ON_WORK = re.compile(r"\bgit\s+(mv|rm)\s[^;&|]*\bwork/")
SHELL_SEPARATOR = frozenset((";", "&&", "||", "|", "&", "(", ")", "\n"))
SHELL_KEYWORD = frozenset(("then", "do", "{"))
COMMAND_WRAPPER = frozenset(("nohup", "sudo", "time", "nice"))
SHELL_COMMAND = frozenset(("bash", "dash", "ksh", "sh", "zsh"))
GIT_OPTION_WITH_VALUE = frozenset(("-C", "-c", "--git-dir", "--work-tree"))
# `<<TAG`, `<<'TAG'`, `<<"TAG"`, and the `<<-` form that strips leading tabs. A quoted
# tag holds any character, so `<<'END-OF-FILE'` matches. An unquoted tag starts with a
# letter or an underscore: a tag that starts with a digit would also match the `<<` of
# an arithmetic shift, and `echo $((1<<2))` would read as a heredoc that opens tag `2`.
HEREDOC_TAG = re.compile(r"<<-?\s*(?:'([^'\n]+)'|\"([^\"\n]+)\"|([A-Za-z_][A-Za-z0-9_.-]*))")


def read_payload(stream=None):
    raw = (stream or sys.stdin).read()
    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except ValueError:
        return {}


def _deny(reason):
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                              "permissionDecision": "deny",
                                              "permissionDecisionReason": reason}}))
    return 0


def _relpath(root, file_path):
    if not file_path:
        return None
    p = file_path if os.path.isabs(file_path) else os.path.join(root, file_path)
    p = os.path.realpath(p)
    r = os.path.realpath(root)
    if not p.startswith(r + os.sep):
        return None
    return os.path.relpath(p, r).replace(os.sep, "/")


def session_start(root, payload):
    report = manifest.doctor(root)
    if report["state"] == "not-initialised":
        r = scaffold.init(root)
        print("harness: the repository was not initialised. init created %d file(s): %s"
              % (len(r["created"]), ", ".join(r["created"][:8]) + (" ..." if len(r["created"]) > 8 else "")))
        report = manifest.doctor(root)
    print(manifest.doctor_text(report))
    print("harness: open the session with `python3 -m harness session open`.")
    return 0


def pre_write(root, payload):
    tool = payload.get("tool_name", "")
    rp = _relpath(root, (payload.get("tool_input") or {}).get("file_path"))
    if rp is None:
        return 0
    if rp in TOOL_OWNED:
        return _deny("%s is written by the harness tool only. Use `python3 -m harness` commands." % rp)
    if rp in USER_OWNED:
        return _deny("%s is user-owned. If the user gave this target in their own words, run "
                     "`python3 -m harness target set <stock> <value> --by user --why \"...\"`." % rp)
    if STATE_FOLDER.search(rp) and tool == "Write" and not os.path.exists(os.path.join(root, rp)):
        return _deny("%s is inside a state folder. The folder is the state. Create a task with "
                     "`python3 -m harness new task --title ... --epic EP-NN`, and move it with start/done/back." % rp)
    if TASK_FILE.search(rp) and _priority_lines_change(payload):
        task_id = re.search(r"TASK-\d{4}", rp).group(0)
        return _deny("this write sets or changes `priority` in %s by hand. A priority carries an author and a "
                     "date, and the user names it. Run `python3 -m harness priority %s --by user --why \"...\"`."
                     % (rp, task_id))
    return 0


def _priority_lines(text):
    return sorted(m.group(0).strip() for m in PRIORITY_LINE.finditer(text or ""))


def _priority_lines_change(payload):
    """True when the written text adds, removes, or changes a `priority*:` line."""
    inp = payload.get("tool_input") or {}
    if payload.get("tool_name") == "Write":
        return bool(_priority_lines(inp.get("content")))
    return _priority_lines(inp.get("new_string")) != _priority_lines(inp.get("old_string"))


def pre_bash(root, payload):
    cmd = (payload.get("tool_input") or {}).get("command", "") or ""
    protected = _protected_git_operation(cmd)
    if protected:
        operation, reason = protected
        return _deny("The hook denied `%s` because %s. Remove the protected operation." %
                     (operation, reason))
    if MOVE_ON_WORK.search(cmd) or GIT_MV_ON_WORK.search(cmd):
        return _deny("this command moves or removes files under work/ by hand. The folder is the state. "
                     "Use `python3 -m harness start|done|back|assign`, or `git rm` through the user.")
    return 0


def _protected_git_operation(command, depth=0):
    """Name a protected Git operation and give the reason for the deny.

    Claude permission rules match command text. The Bash hook receives the full
    command. The hook checks each shell segment before the shell runs it.
    """
    if depth > 3:
        return ("nested shell command", "the hook cannot inspect more than three shell levels")
    words = _lex(_strip_heredocs(command))
    if words is None:
        return ("unparsed shell command", "the hook cannot inspect its quoting safely")
    segment = []
    for word in words + [";"]:
        if word not in SHELL_SEPARATOR:
            segment.append(word)
            continue
        operation = _protected_git_segment(segment, depth)
        if operation:
            return operation
        segment = []
    return None


def _strip_heredocs(command):
    """Return the command with every heredoc body removed.

    A heredoc body is data for another program. The shell never runs it as a command,
    so the hook has nothing to read there. The body also holds quotes that no shell
    reads as quotes, and a lexer that reads them fails on an ordinary commit message.

    Measured on 2026-09-06: `git commit -F - <<'EOF'` with the word `doesn't` in the
    message denied the commit. The heredoc marker stays on its line, so a protected
    command that carries a heredoc is still read and still denied.
    """
    lines = command.split("\n")
    kept = []
    index = 0
    while index < len(lines):
        line = lines[index]
        kept.append(line)
        index += 1
        for tag in _heredoc_tags(line):
            end = index
            while end < len(lines) and lines[end].strip() != tag:
                end += 1
            if end < len(lines):
                index = end + 1  # the body and its terminator carry no command
            # No terminator line: keep every line. A tag that this regex reads wrongly
            # would otherwise remove the rest of the command, and a `git push --force`
            # below an unterminated heredoc would never be read.
    return "\n".join(kept)


def _heredoc_tags(line):
    """Return the heredoc tag of each `<<` on one line."""
    return [next(g for g in m.groups() if g is not None) for m in HEREDOC_TAG.finditer(line)]


def _drop_comments(command):
    """Return the command with a trailing `#` comment removed from EVERY line.

    The comment of one line must never remove another line. An earlier form searched
    the whole command and cut from the first `#` to the end of the text. Measured on
    2026-09-06: `echo # '` on line 1 removed `git push --force` on line 2, and the
    guard allowed the push. A comment ends at its own newline, and so does this.
    """
    kept = []
    for line in command.split("\n"):
        found = re.search(r"(?:^|[\s;&|()])#", line)
        kept.append(line[:found.start()] if found else line)
    return "\n".join(kept)


def _lex(command):
    """Return the words of the whole command, or None when the hook cannot read it.

    The lexer reads the command once, and never one line at a time. A line is not a
    unit of shell syntax: a quoted string, a `python3 -c` program, and a heredoc all
    cross a newline. A lexer that reads one line at a time cuts them, sees an odd
    number of quotes, and denies an ordinary command.

    A newline leaves the whitespace set and joins the punctuation set, so it becomes
    one token. Two commands on two lines stay two segments, and a quoted string that
    holds a newline stays one word.

    A command that fails once can carry a trailing comment. The shell drops a comment
    before it runs the command, so the hook drops it too, one line at a time. A
    command that still fails is a command that the hook must not guess at.
    """
    for text in (command, _drop_comments(command)):
        try:
            lexer = shlex.shlex(text, posix=True, punctuation_chars=";&|()\n")
            lexer.whitespace_split = True
            lexer.commenters = ""
            lexer.whitespace = " \t\r"
            return list(lexer)
        except ValueError:
            continue
    return None


def _protected_git_segment(words, depth=0):
    index = 0
    while index < len(words) and words[index] in SHELL_KEYWORD:
        index += 1
    while index < len(words) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", words[index]):
        index += 1
    while index < len(words) and os.path.basename(words[index]) in ("command", "exec", "env"):
        wrapper = os.path.basename(words[index])
        index += 1
        if wrapper == "env":
            while index < len(words) and (words[index].startswith("-") or "=" in words[index]):
                index += 1
    while index < len(words) and os.path.basename(words[index]) in COMMAND_WRAPPER:
        wrapper = os.path.basename(words[index])
        index += 1
        if wrapper == "sudo":
            index = _skip_sudo_options(words, index)
        elif wrapper == "nice":
            index = _skip_nice_options(words, index)
        else:
            while index < len(words) and words[index].startswith("-"):
                index += 1
    if index >= len(words):
        return None

    executable = os.path.basename(words[index])
    if executable in SHELL_COMMAND:
        shell_args = words[index + 1:]
        command_at = next((i for i, word in enumerate(shell_args) if word == "-c"), None)
        if command_at is not None and command_at + 1 < len(shell_args):
            return _protected_git_operation(shell_args[command_at + 1], depth + 1)
        return None
    if executable != "git":
        return None

    words = words[index + 1:]
    command_at = _git_subcommand_index(words)
    if command_at is None:
        return None
    command = words[command_at]
    args = words[command_at + 1:]
    if command == "commit":
        flag = next((arg for arg in args if arg == "--amend" or arg.startswith("--amend=")), None)
        if flag:
            return ("git commit %s" % flag, "%s rewrites the last commit" % flag)
    if command == "push":
        for arg in args:
            protected_arg = _protected_push_arg(arg)
            if protected_arg:
                return ("git push %s" % protected_arg,
                        "%s can rewrite or remove remote history" % protected_arg)
    return None


def _skip_sudo_options(words, index):
    """Return the command index after supported sudo options."""
    with_value = ("-C", "-D", "-g", "-h", "-p", "-R", "-r", "-t", "-u",
                  "--chdir", "--close-from", "--group", "--host", "--prompt",
                  "--role", "--type", "--user")
    while index < len(words):
        word = words[index]
        if word == "--":
            return index + 1
        if word in with_value:
            index += 2
            continue
        if word.startswith("-"):
            index += 1
            continue
        return index
    return index


def _skip_nice_options(words, index):
    """Return the command index after supported nice options."""
    if index < len(words) and words[index] in ("-n", "--adjustment"):
        return min(index + 2, len(words))
    if index < len(words) and re.fullmatch(r"-\d+", words[index]):
        return index + 1
    return index


def _git_subcommand_index(words):
    """Return the index of the first non-option Git word."""
    index = 0
    while index < len(words):
        word = words[index]
        if word == "--":
            return index + 1 if index + 1 < len(words) else None
        if word in GIT_OPTION_WITH_VALUE:
            index += 2
            continue
        if word.startswith(("--git-dir=", "--work-tree=")):
            index += 1
            continue
        if word.startswith("-"):
            index += 1
            continue
        return index
    return None


def _protected_push_arg(arg):
    """Return the protected push argument, or return None."""
    if arg in ("--force", "--force-with-lease") or arg.startswith(("--force=", "--force-with-lease=")):
        return arg
    if arg in ("--delete", "-d"):
        return arg
    if arg.startswith("+") or arg.startswith(":") or arg.endswith(":"):
        return arg
    if arg.startswith("-") and not arg.startswith("--") and "f" in arg[1:]:
        return arg
    return None


def _touches_work(root, payload):
    tool = payload.get("tool_name", "")
    inp = payload.get("tool_input") or {}
    if tool in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        rp = _relpath(root, inp.get("file_path"))
        return bool(rp and rp.startswith("work/"))
    if tool == "Bash":
        cmd = inp.get("command", "") or ""
        return "work/" in cmd or "-m harness" in cmd
    return False


def post_work(root, payload):
    if not _touches_work(root, payload):
        return 0
    if not os.path.isdir(os.path.join(root, "work")):
        return 0
    tree = scan(root)
    errors, warnings = board.check(tree, wip_cap=state.wip_cap(root))
    if errors:
        sys.stderr.write("harness check is RED after this change:\n")
        for e in errors:
            sys.stderr.write("  error " + e + "\n")
        for w in warnings:
            sys.stderr.write("  warn  " + w + "\n")
        return 2
    print("harness check: GREEN (%d task(s), %d warning(s))" % (len(all_tasks(tree)), len(warnings)))
    for w in warnings:
        print("  warn  " + w)
    return 0


def stop(root, payload):
    if payload.get("stop_hook_active"):
        return 0
    if not os.path.isdir(os.path.join(root, "work")):
        return 0
    tree = scan(root)
    waiting = [t for t in all_tasks(tree) if t.state == "in-progress" and t.needs_eye()]
    late = overdue(tree)
    if not waiting and not late:
        return 0
    parts = []
    if waiting:
        parts.append("%d task(s) wait for a human verdict: %s" % (len(waiting), ", ".join(t.id for t in waiting)))
    for sp, left in late:
        parts.append("%s ended on %s with %d open task(s)" % (sp.id, sp.ends, len(left)))
    print(json.dumps({"systemMessage": "harness: " + ". ".join(parts) + "."}))
    return 0


def session_end(root, payload):
    if not manifest.exists(root):
        return 0
    written = state.observe(root)
    if written:
        print("harness: %d observation(s) appended to %s" % (len(written), rel(root, os.path.join(root, ".harness", "journal.jsonl"))))
    return 0


HOOKS = {
    "session-start": session_start,
    "pre-write": pre_write,
    "pre-bash": pre_bash,
    "post-work": post_work,
    "stop": stop,
    "session-end": session_end,
}


def run(root, name, stream=None):
    fn = HOOKS.get(name)
    if fn is None:
        print("harness hook: unknown hook %s. Known: %s" % (name, ", ".join(HOOKS)))
        return 0
    payload = read_payload(stream)
    try:
        return fn(root, payload)
    except Exception as exc:  # a hook never breaks the session
        print("harness hook %s: %s" % (name, exc))
        return 0
