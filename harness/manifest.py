"""The manifest and the integrity gate.

`.harness/manifest.json` records the harness version, the creation date, the project
profile, and every installed file with its kind. `doctor` reads it and reports one of
three states: not initialised (exit 2), damaged (exit 1), sound (exit 0).

Doctor measures live signals, not only checksums. A path that exists does not prove
that the path is correct (law 3). So doctor also parses the hooks in settings.json,
parses every journal line, and compares the recorded version with the package.
"""
import json
import os
import sys

from harness import MIN_PYTHON, VERSION
from harness.util import HarnessError, now_iso, read_text, sha256_file, write_text

PATH = os.path.join(".harness", "manifest.json")
KINDS = ("owned", "seeded")

# The hook commands that settings.json must carry. Doctor checks each one.
REQUIRED_HOOKS = {
    "SessionStart": "python3 -m harness hook session-start",
    "PreToolUse": "python3 -m harness hook pre-write",
    "PostToolUse": "python3 -m harness hook post-work",
    "Stop": "python3 -m harness hook stop",
    "SessionEnd": "python3 -m harness hook session-end",
}


def path(root):
    return os.path.join(root, PATH)


def exists(root):
    return os.path.exists(path(root))


def load(root):
    p = path(root)
    if not os.path.exists(p):
        return None
    try:
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    except ValueError as exc:
        raise HarnessError("%s is not valid JSON: %s. Run `python3 -m harness init --rebuild-manifest`." % (PATH, exc))


def save(root, data):
    write_text(path(root), json.dumps(data, indent=2, ensure_ascii=False, sort_keys=False) + "\n")


def new(profile=None, rules_path="CLAUDE.md"):
    return {
        "$comment": "The harness writes this file. Do not edit it by hand. `doctor` reads it.",
        "harness_version": VERSION,
        "created_at": now_iso(),
        "rules_path": rules_path,
        "profile": profile or {"architecture": "", "languages": [], "purpose": "", "end_user": ""},
        "files": {},
    }


def record(data, relpath, kind, abspath=None, template=None):
    if kind not in KINDS:
        raise ValueError("kind must be one of %s" % (KINDS,))
    entry = {"kind": kind}
    if template:
        entry["template"] = template
    if kind == "owned" and abspath:
        entry["sha256"] = sha256_file(abspath)
    data["files"][relpath] = entry
    return entry


def _hooks_present(root):
    """Return (missing hook names, error text). Parse the file: a present file is not a working file."""
    p = os.path.join(root, ".claude", "settings.json")
    if not os.path.exists(p):
        return list(REQUIRED_HOOKS), ".claude/settings.json is missing"
    try:
        data = json.loads(read_text(p))
    except ValueError as exc:
        return list(REQUIRED_HOOKS), ".claude/settings.json is not valid JSON: %s" % exc
    hooks = data.get("hooks") or {}
    missing = []
    for event, needle in REQUIRED_HOOKS.items():
        found = False
        for entry in hooks.get(event) or []:
            for h in entry.get("hooks") or []:
                if needle in str(h.get("command", "")):
                    found = True
        if not found:
            missing.append(event)
    return missing, ""


def doctor(root):
    """Return a report dict with `state` in {not-initialised, damaged, sound} and `exit`."""
    report = {"root": root, "harness_version": VERSION, "state": "sound", "exit": 0,
              "problems": [], "notes": [], "files_checked": 0}

    def damaged(what, fix, kind=None):
        report["state"] = "damaged"
        report["exit"] = 1
        problem = {"what": what, "fix": fix}
        if kind:
            problem["kind"] = kind
        report["problems"].append(problem)

    if sys.version_info < MIN_PYTHON:
        damaged("Python %d.%d runs this harness, and it needs %d.%d or later"
                % (sys.version_info[0], sys.version_info[1], MIN_PYTHON[0], MIN_PYTHON[1]),
                "run the harness with python3.%d or later" % MIN_PYTHON[1])
    data = load(root)
    if data is None:
        report.update({"state": "not-initialised", "exit": 2})
        report["problems"].append({"what": "no %s" % PATH, "fix": "run `python3 -m harness init`"})
        return report
    report["manifest_version"] = data.get("harness_version")
    report["created_at"] = data.get("created_at")
    if data.get("harness_version") != VERSION:
        damaged("the manifest records harness %s and the package is %s" % (data.get("harness_version"), VERSION),
                "run `python3 -m harness upgrade`")
    for relpath, entry in sorted((data.get("files") or {}).items()):
        report["files_checked"] += 1
        abspath = os.path.join(root, relpath)
        if not os.path.exists(abspath):
            owned = entry.get("kind") == "owned"
            damaged("%s is missing (%s)" % (relpath, entry.get("kind")),
                    "run `python3 -m harness restore %s`" % relpath if owned
                    else "run `python3 -m harness init` to seed it again",
                    kind="missing-owned" if owned else "missing-seeded")
            continue
        if entry.get("kind") == "owned":
            actual = sha256_file(abspath)
            if actual != entry.get("sha256"):
                damaged("%s differs from the checksum in the manifest" % relpath,
                        "run `python3 -m harness restore %s` to get the template back, or "
                        "`python3 -m harness adopt %s` to record your edit" % (relpath, relpath))
    missing, err = _hooks_present(root)
    if err:
        damaged(err, "run `python3 -m harness hooks install`")
    elif missing:
        damaged("the hooks for %s are missing from .claude/settings.json" % ", ".join(missing),
                "run `python3 -m harness hooks install`")
    from harness import journal
    _, bad = journal.read(root)
    for n, text in bad:
        damaged("%s line %d is not JSON: %s" % (journal.PATH, n, text), "fix or remove that line. The journal is append only.")
    profile = data.get("profile") or {}
    empty = [k for k in ("architecture", "languages", "purpose", "end_user") if not profile.get(k)]
    if empty:
        report["notes"].append("the profile has no %s. Run `python3 -m harness profile ask`." % ", ".join(empty))
    return report


def only_missing_seeded(report):
    """True when every problem is a seeded file that `init` writes again.

    A repository can ignore its own board in git. A clone then lacks every seeded
    file, and `doctor` turns red on a state that one `init` fixes. This test tells a
    caller that `init` is the whole fix. An owned file with a wrong checksum, a wrong
    manifest version, or a missing hook never passes this test.
    """
    problems = report.get("problems") or []
    return bool(problems) and all(p.get("kind") == "missing-seeded" for p in problems)


def doctor_text(report):
    lines = []
    label = {"sound": "HARNESS: sound", "damaged": "HARNESS: damaged", "not-initialised": "HARNESS: not initialised"}
    lines.append("%s (package %s, manifest %s, %d file(s) checked)"
                 % (label[report["state"]], report["harness_version"], report.get("manifest_version") or "-", report["files_checked"]))
    for p in report["problems"]:
        lines.append("  [X] %s" % p["what"])
        lines.append("      fix: %s" % p["fix"])
    for n in report["notes"]:
        lines.append("  [i] %s" % n)
    return "\n".join(lines)
