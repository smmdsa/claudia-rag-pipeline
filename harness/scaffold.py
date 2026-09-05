"""init, upgrade, uninstall, adopt, restore, and the hook installer.

`harness/templates/` holds every file that `init` installs. The relative path inside
`templates/` is the destination inside the repository, with two exceptions:
  CLAUDE.md          goes to CLAUDE.md when none exists, else to .claude/rules/harness.md
  gitignore.lines    its lines are added to .gitignore when they are missing

Three kinds of file. `owned` files are the harness's: doctor checks their checksum.
`seeded` files are the project's after the first write: doctor checks that they exist.
`SEED_TASK` is the adopter's first task: the manifest never records it, because the
adopter moves it across the board.
`init` never overwrites a file (law 12).
"""
import difflib
import json
import os
import shutil

from harness import VERSION, manifest
from harness.util import HarnessError, read_text, rel, sha256_file, write_text

TEMPLATES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")

# Files the project edits after the first write. Everything else is owned.
SEEDED = {
    "work/ROADMAP.md",
    "work/backlog/README.md",
    "docs/ACTIVITY.md",
    "docs/session-log.md",
    ".harness/targets.json",
    ".harness/escalations.md",
    ".harness/journal.jsonl",
    ".claude/settings.json",
    ".mcp.json",
    ".gitignore",
    "infra/rag/config/index.yml",
}

# Directories that init creates empty, with a .gitkeep.
KEEP_DIRS = ("work/sprints", "work/backlog", "docs/sessions")

SPECIAL = {"CLAUDE.md", "gitignore.lines"}

# The adopter's first task. `init` writes it once, and the manifest never records it.
# The adopter moves this file across the board, and `doctor` asks for every file that
# the manifest records. A tracked task would turn `doctor` red on the first `done`.
SEED_TASK = "work/backlog/TASK-0001-start-the-harness-in-this-repository.md"

# Migration steps between versions. Each entry: (from, to, function(root) -> list of notes).
MIGRATIONS = []


def template_files():
    out = []
    for dirpath, dirs, files in os.walk(TEMPLATES):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for f in files:
            if f.endswith((".pyc", ".pyo")):
                continue
            full = os.path.join(dirpath, f)
            out.append(os.path.relpath(full, TEMPLATES).replace(os.sep, "/"))
    return sorted(out)


def render(relpath, project):
    text = read_text(os.path.join(TEMPLATES, relpath))
    return text.replace("{{PROJECT}}", project).replace("{{HARNESS_VERSION}}", VERSION)


def project_name(root):
    return os.path.basename(os.path.realpath(root)).lower() or "project"


def _ensure_lines(path, lines):
    have = read_text(path).splitlines() if os.path.exists(path) else []
    missing = [l for l in lines if l and l not in have]
    if missing:
        text = "\n".join(have + missing) + "\n" if have else "\n".join(missing) + "\n"
        write_text(path, text)
    return missing


def _merge_hooks(root, template_json):
    """Add the harness hooks to an existing settings.json. Keep every other key."""
    p = os.path.join(root, ".claude", "settings.json")
    wanted = json.loads(template_json)
    try:
        data = json.loads(read_text(p)) if os.path.exists(p) else {}
    except ValueError as exc:
        raise HarnessError(".claude/settings.json is not valid JSON: %s. Fix it, then run init again." % exc)
    hooks = data.setdefault("hooks", {})
    added = []
    for event, entries in wanted["hooks"].items():
        have = hooks.setdefault(event, [])
        for entry in entries:
            commands = {h.get("command") for h in entry.get("hooks", [])}
            present = any(
                {h.get("command") for h in e.get("hooks", [])} & commands for e in have
            )
            if not present:
                have.append(entry)
                added.append(event)
    for key in ("deny",):
        perms = data.setdefault("permissions", {})
        have = perms.setdefault(key, [])
        for rule in wanted.get("permissions", {}).get(key, []):
            if rule not in have:
                have.append(rule)
    write_text(p, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    return added


def has_task(root):
    """True when work/ already holds a task file. `work/templates/` does not count."""
    base = os.path.join(root, "work")
    for dirpath, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d != "templates"]
        for name in files:
            if name.startswith("TASK-") and name.endswith(".md"):
                return True
    return False


def init(root, rebuild_manifest=False):
    """Create every missing file. Keep every present file. Idempotent."""
    project = project_name(root)
    data = manifest.load(root)
    if data is None or rebuild_manifest:
        data = manifest.new(profile=(data or {}).get("profile") if data else None)
    created, kept, notes = [], [], []
    rules_dest = data.get("rules_path") or "CLAUDE.md"
    if not manifest.exists(root) or rebuild_manifest:
        if os.path.exists(os.path.join(root, "CLAUDE.md")) and "CLAUDE.md" not in (data.get("files") or {}):
            rules_dest = os.path.join(".claude", "rules", "harness.md").replace(os.sep, "/")
            notes.append("CLAUDE.md exists. The rules go to %s. Claude Code loads both." % rules_dest)
    data["rules_path"] = rules_dest

    for relpath in template_files():
        if relpath == "gitignore.lines":
            missing = _ensure_lines(os.path.join(root, ".gitignore"), render(relpath, project).splitlines())
            manifest.record(data, ".gitignore", "seeded", template=relpath)
            (created if missing else kept).append(".gitignore")
            continue
        if relpath == SEED_TASK:
            dest = os.path.join(root, *SEED_TASK.split("/"))
            if os.path.exists(dest) or has_task(root):
                kept.append(SEED_TASK)
                continue
            write_text(dest, render(relpath, project))
            created.append(SEED_TASK + "  (your first task. The harness does not track it.)")
            continue
        dest_rel = rules_dest if relpath == "CLAUDE.md" else relpath
        dest = os.path.join(root, dest_rel)
        kind = "seeded" if dest_rel in SEEDED else "owned"
        if relpath == ".claude/settings.json" and os.path.exists(dest):
            added = _merge_hooks(root, render(relpath, project))
            manifest.record(data, dest_rel, "seeded", template=relpath)
            (created if added else kept).append(dest_rel + (" (hooks merged)" if added else ""))
            continue
        if os.path.exists(dest):
            if dest_rel not in data["files"]:
                # A file the project already had. It is the project's. Doctor checks only that it exists.
                manifest.record(data, dest_rel, "seeded", template=relpath)
                notes.append("%s existed before init. It is recorded as seeded, not owned." % dest_rel)
            kept.append(dest_rel)
            continue
        write_text(dest, render(relpath, project))
        if relpath.endswith(".sh"):
            os.chmod(dest, 0o755)
        manifest.record(data, dest_rel, kind, abspath=dest, template=relpath)
        created.append(dest_rel)
    for d in KEEP_DIRS:
        keep = os.path.join(root, d, ".gitkeep")
        if not os.path.exists(keep):
            write_text(keep, "")
            created.append(d + "/.gitkeep")
    manifest.save(root, data)
    return {"root": root, "project": project, "created": created, "kept": kept, "notes": notes,
            "manifest": rel(root, manifest.path(root)), "rules_path": rules_dest}


def init_text(r):
    lines = ["init: %d file(s) created, %d kept, manifest at %s" % (len(r["created"]), len(r["kept"]), r["manifest"])]
    for c in r["created"]:
        lines.append("  + " + c)
    for n in r["notes"]:
        lines.append("  note: " + n)
    lines.append("")
    lines.append("Run `python3 -m harness help` to read what init created and what you own.")
    if any(c.startswith(SEED_TASK) for c in r["created"]):
        lines.append("Your board holds your first task. Run `python3 -m harness next` to read it.")
    else:
        lines.append("next: `python3 -m harness profile ask`, then `python3 -m harness doctor`.")
    return "\n".join(lines)


def _owned(data):
    return {p: e for p, e in (data.get("files") or {}).items() if e.get("kind") == "owned"}


def adopt(root, relpath):
    data = manifest.load(root)
    if data is None:
        raise HarnessError("not initialised. Run `python3 -m harness init`.")
    entry = data["files"].get(relpath)
    if entry is None:
        raise HarnessError("%s is not in the manifest." % relpath)
    abspath = os.path.join(root, relpath)
    if not os.path.exists(abspath):
        raise HarnessError("%s does not exist." % relpath)
    entry["sha256"] = sha256_file(abspath)
    entry["adopted"] = True
    manifest.save(root, data)
    return {"adopted": relpath, "sha256": entry["sha256"]}


def diff_against_template(root, relpath, project=None):
    data = manifest.load(root)
    entry = (data or {}).get("files", {}).get(relpath)
    if entry is None or not entry.get("template"):
        raise HarnessError("%s is not an installed file with a template." % relpath)
    wanted = render(entry["template"], project or project_name(root))
    have = read_text(os.path.join(root, relpath)) if os.path.exists(os.path.join(root, relpath)) else ""
    return "".join(difflib.unified_diff(have.splitlines(True), wanted.splitlines(True),
                                        fromfile=relpath, tofile="template/" + entry["template"]))


def restore(root, relpath):
    data = manifest.load(root)
    if data is None:
        raise HarnessError("not initialised. Run `python3 -m harness init`.")
    entry = data["files"].get(relpath)
    if entry is None or not entry.get("template"):
        raise HarnessError("%s is not an installed file with a template." % relpath)
    diff = diff_against_template(root, relpath)
    abspath = os.path.join(root, relpath)
    write_text(abspath, render(entry["template"], project_name(root)))
    if entry["template"].endswith(".sh"):
        os.chmod(abspath, 0o755)
    entry["sha256"] = sha256_file(abspath)
    entry.pop("adopted", None)
    manifest.save(root, data)
    return {"restored": relpath, "diff": diff}


def upgrade(root):
    data = manifest.load(root)
    if data is None:
        raise HarnessError("not initialised. Run `python3 -m harness init`.")
    old = old_version = data.get("harness_version")
    rewritten, edited, notes = [], [], []
    project = project_name(root)
    for relpath, entry in _owned(data).items():
        abspath = os.path.join(root, relpath)
        if not entry.get("template"):
            continue
        if os.path.exists(abspath) and sha256_file(abspath) != entry.get("sha256"):
            edited.append(relpath)
            continue
        write_text(abspath, render(entry["template"], project))
        entry["sha256"] = sha256_file(abspath)
        rewritten.append(relpath)
    for start, end, fn in MIGRATIONS:
        if old == start:
            notes.extend(fn(root))
            old = end
    data["harness_version"] = VERSION
    manifest.save(root, data)
    r = init(root)
    return {"from": old_version, "to": VERSION, "rewritten": rewritten,
            "edited_kept": edited, "created": r["created"], "notes": notes}


def uninstall(root, dry_run=True):
    data = manifest.load(root)
    if data is None:
        raise HarnessError("not initialised. Nothing to remove.")
    remove, keep = [], []
    for relpath, entry in sorted(data["files"].items()):
        abspath = os.path.join(root, relpath)
        if not os.path.exists(abspath):
            continue
        if entry.get("kind") == "owned" and sha256_file(abspath) == entry.get("sha256"):
            remove.append(relpath)
        else:
            keep.append((relpath, "seeded, the project owns it" if entry.get("kind") == "seeded" else "edited since install"))
    if not dry_run:
        for relpath in remove:
            os.remove(os.path.join(root, relpath))
            d = os.path.dirname(os.path.join(root, relpath))
            while d != root and os.path.isdir(d) and not os.listdir(d):
                os.rmdir(d)
                d = os.path.dirname(d)
        os.remove(manifest.path(root))
    return {"dry_run": dry_run, "removed": remove, "kept": keep,
            "note": "the harness/ package directory and the work tree stay. Remove them by hand when you want."}


def install_hooks(root):
    template = render(".claude/settings.json", project_name(root))
    added = _merge_hooks(root, template)
    data = manifest.load(root)
    if data is not None:
        manifest.record(data, ".claude/settings.json", "seeded", template=".claude/settings.json")
        manifest.save(root, data)
    return {"added": added}
