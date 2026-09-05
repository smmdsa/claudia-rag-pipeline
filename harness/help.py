"""The adopter's map. `python3 -m harness help [topic]`.

This module holds no rule. The rules live in `CLAUDE.md`, `work/README.md`, and
`docs/DESIGN-LAWS.md`. Every section names the file that holds the rule (law 2).

The map reads the repository on every run. `help skills` lists what
`.claude/skills/` holds now. `help board` and `help eye` print the values that
`harness.board` declares now. A hard-coded list rots in silence (law 1).
"""
import os
import textwrap

from harness import VERSION, board, frontmatter, ports

TOPICS = ("board", "eye", "skills", "rag")

SKILLS_DIR = ".claude/skills"

WIDTH = 78


def rules_file(root):
    """Name the file that holds the rules. `init` writes one of the two."""
    if os.path.exists(os.path.join(root, ".claude", "rules", "harness.md")):
        return ".claude/rules/harness.md"
    return "CLAUDE.md"


def _first_sentence(text):
    """Cut at the first sentence end, or at the first colon. Keep the line short."""
    text = " ".join(str(text).split())
    for i, ch in enumerate(text):
        if ch == ":":
            return text[:i] + "."
        if ch == "." and (i + 1 == len(text) or text[i + 1] == " "):
            return text[:i + 1]
    return text


def skills(root):
    """One row per installed skill, read from `.claude/skills/*/SKILL.md`."""
    base = os.path.join(root, *SKILLS_DIR.split("/"))
    out = []
    if not os.path.isdir(base):
        return out
    for name in sorted(os.listdir(base)):
        path = os.path.join(base, name, "SKILL.md")
        if not os.path.isfile(path):
            continue
        fields, _ = frontmatter.read(path)
        out.append({"name": fields.get("name") or name,
                    "when": _first_sentence(fields.get("description") or "(no description)"),
                    "path": "%s/%s/SKILL.md" % (SKILLS_DIR, name)})
    return out


def _mark(root, relpath, note):
    """Name a path, and say so when the path is missing (law 3)."""
    there = os.path.exists(os.path.join(root, *relpath.split("/")))
    return [relpath, note if there else note + "  (MISSING — run `init`)"]


def _overview(root):
    rules = rules_file(root)
    return [
        {"heading": "WHAT THIS IS", "items": [
            ["", "An agent pipeline and a work board. Both live in git, next to"],
            ["", "the code. This command is a map. The rules live in the files"],
            ["", "that the map names."]]},
        {"heading": "WHAT INIT CREATED", "items": [
            _mark(root, "work/", "the board. One folder per state. The tree is the truth."),
            _mark(root, ".claude/", "the skills and the hooks that Claude Code runs."),
            _mark(root, ".harness/", "the manifest, the journal, and your targets."),
            _mark(root, "docs/", "the design laws, the session log, and the fronts."),
            _mark(root, rules, "the rules that the agent reads before an edit.")]},
        {"heading": "WHAT YOU OWN", "items": [
            ["a verdict", "The agent never closes an `eye` task without your words."],
            ["a target", "You declare every target. The tool measures the gap."],
            ["a priority", "You name the next task. The agent never ranks for you."],
            ["the roadmap", "You write `work/ROADMAP.md`. The board computes status."],
            ["", "The full boundary lives in %s." % rules]]},
        {"heading": "WHAT THE AGENT DOES ALONE", "items": [
            ["", "It reads every file, creates a task, moves its own work, and"],
            ["", "closes a task with `eye: NONE`. Above that line it stops and"],
            ["", "runs `python3 -m harness escalate`."]]},
        {"heading": "YOUR FIRST FIVE MINUTES", "items": [
            ["1", "python3 -m harness profile ask      answer four questions"],
            ["2", "python3 -m harness skills generate  write the project skills"],
            ["3", "python3 -m harness next             read your first task"],
            ["4", "python3 -m harness doctor           it must exit 0"]]},
        {"heading": "WHERE THE RULES LIVE", "items": [
            _mark(root, rules, "the rules for the agent, the glossary, and the laws."),
            _mark(root, "work/README.md", "the rules of the board, and the two sizes."),
            ["", "%s holds the twelve laws in short form. The harness" % rules],
            ["", "repository records the measured failure behind each law in"],
            ["", "docs/DESIGN-LAWS.md. `init` does not copy that record."]]},
        {"heading": "MORE", "items": [
            ["", "python3 -m harness help %s" % " | ".join(TOPICS)],
            ["", "python3 -m harness --help   every command, one line each"]]},
    ]


def _board(root):
    return [
        {"heading": "THE BOARD IS COMPUTED", "items": [
            ["", "A task file lives in one state folder, and that folder IS its"],
            ["", "state. No file stores a status or a count. Run the tool and it"],
            ["", "computes the board from the tree."]]},
        {"heading": "THE STATES", "items": [
            ["", " -> ".join(board.STATES) + "   (from harness.board.STATES)"]]},
        {"heading": "THE WORK SIZES", "items": [
            ["", ", ".join(board.WORK) + "   (from harness.board.WORK)"],
            ["", "work/README.md holds the meaning of each size."]]},
        {"heading": "THE DAILY COMMANDS", "items": [
            ["board", "the whole picture"],
            ["next", "the first task the agent can start now"],
            ["start <id>", "todo -> in-progress"],
            ["done <id>", "in-progress -> done. An eye task needs --verdict."],
            ["check", "measure the SHAPE of the tree. Exit 1 on an error."],
            ["clock", "the days that remain in each sprint"]]},
        {"heading": "WHAT CHECK DOES NOT DO", "items": [
            ["", "`check` never measures whether a task is correct. It measures"],
            ["", "the shape of the tree. A green `check` proves nothing about"],
            ["", "the software."]]},
        {"heading": "THE FULL RULES", "items": [
            _mark(root, "work/README.md", "the layout, the fields, and the two sizes.")]},
    ]


def _eye(root):
    return [
        {"heading": "TWO SIZES, NOT ONE", "items": [
            ["", "`work` measures the agent's cost. `eye` measures yours. The"],
            ["", "measured bottleneck of an agent-driven project is your eye,"],
            ["", "not agent hours."]]},
        {"heading": "THE EYE VALUES", "items": [
            ["", ", ".join(board.EYE) + "   (from harness.board.EYE)"],
            ["", "work/README.md holds the meaning of each value."]]},
        {"heading": "WHAT THE TOOL REFUSES", "items": [
            ["", "`done` on a task with `eye: GLANCE` or `eye: RUN` fails without"],
            ["", "--verdict. The agent cannot write that verdict. You give the"],
            ["", "words, and the tool records who gave them and when."]]},
        {"heading": "HOW TO CLOSE AN EYE TASK", "items": [
            ["", 'python3 -m harness done TASK-0004 --verdict "it works" --by user']]},
        {"heading": "EYE IS NOT OWNER", "items": [
            ["eye", "WHO closes the task."],
            ["owner", "WHO does the work."],
            ["", "`next` reports `owner: user` tasks first, so they never go quiet."]]},
        {"heading": "THE FULL RULES", "items": [
            _mark(root, "work/README.md", "the eye table, and the measured failure behind it.")]},
    ]


def _skills(root):
    rows = skills(root)
    if not rows:
        return [{"heading": "NO SKILL INSTALLED", "items": [
            ["", "%s holds no SKILL.md. Run `python3 -m harness init`, then" % SKILLS_DIR],
            ["", "`python3 -m harness skills generate`."]]}]
    items = []
    for row in rows:
        items.append([row["name"], row["when"]])
    return [
        {"heading": "HOW A SKILL RUNS", "items": [
            ["", "Claude Code reads the description of every skill. It runs the"],
            ["", "skill when your words match. You type `/session-start`, or you"],
            ["", "say \"let's begin\", and the same skill runs."]]},
        {"heading": "INSTALLED SKILLS (%d)" % len(rows), "items": items},
        {"heading": "WHERE THEY LIVE", "items": [
            ["", "%s/<name>/SKILL.md" % SKILLS_DIR],
            ["", "`python3 -m harness skills generate` writes the project skills"],
            ["", "from the answers of `python3 -m harness profile ask`."]]},
    ]


def _rag(root):
    items = []
    for var, (default, service) in sorted(ports.DEFAULTS.items(), key=lambda kv: kv[1][0]):
        live = ports.port_for(var)
        note = "" if live == default else "  (set to %d)" % live
        items.append([str(default), "%s  %s%s" % (var, service, note)])
    return [
        {"heading": "THE SEARCH INDEX IS OPTIONAL", "items": [
            ["", "The harness runs without it. When the index is down, the agent"],
            ["", "searches with grep, and grep misses the string form of a name."],
            ["", "The session brief says `RAG: BROKEN` when that happens."]]},
        {"heading": "THE PORTS", "items": items or [["", "run `python3 -m harness ports`"]]},
        {"heading": "THE COMMANDS", "items": [
            ["", "python3 -m harness env          derive .harness/env.local"],
            ["", "python3 -m harness ports        every port must be free"],
            ["", "./infra/rag/up.sh               start it. --gpu for CUDA."],
            ["", "python3 -m harness rag health   OK · warnings · BROKEN"],
            ["", "python3 -m harness rag link     did the index start after this agent?"]]},
        {"heading": "THE MOUNT IS READ ONLY", "items": [
            ["", "The stack mounts the repository read only. infra/rag/README.md"],
            ["", "holds the command that proves it."]]},
        {"heading": "THE FULL RULES", "items": [
            _mark(root, "infra/rag/README.md", "the two services, the ports, and the statuses.")]},
    ]


BUILDERS = {"board": _board, "eye": _eye, "skills": _skills, "rag": _rag}


def report(root, topic=None):
    """Return the map as data. `topic` is None for the overview."""
    if topic is None:
        return {"version": VERSION, "topic": "overview", "topics": list(TOPICS),
                "sections": _overview(root)}
    if topic not in BUILDERS:
        from harness.util import HarnessError
        raise HarnessError("no help topic %r. The topics are: %s." % (topic, ", ".join(TOPICS)))
    return {"version": VERSION, "topic": topic, "topics": list(TOPICS),
            "sections": BUILDERS[topic](root)}


def help_text(r):
    title = "HARNESS %s" % r["version"]
    if r["topic"] != "overview":
        title += " — %s" % r["topic"]
    lines = ["=== %s ===" % title]
    for section in r["sections"]:
        lines.append("")
        lines.append(section["heading"])
        pairs = [((item + ["", ""])[0], (item + ["", ""])[1]) for item in section["items"]]
        width = max([len(left) for left, _ in pairs if left] or [0])
        pad = "  " + " " * (width + 2)
        for left, right in pairs:
            if not left:
                lines.append("  %s" % right)
                continue
            chunks = textwrap.wrap(right, max(20, WIDTH - len(pad))) or [""]
            lines.append(("  %-*s  %s" % (width, left, chunks[0])).rstrip())
            lines.extend(pad + chunk for chunk in chunks[1:])
    if r["topic"] == "overview":
        return "\n".join(lines)
    lines.append("")
    lines.append("BACK: python3 -m harness help")
    return "\n".join(lines)
