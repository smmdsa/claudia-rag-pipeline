"""The project profile and the generated skills.

The profile answers four questions: architecture, languages, purpose, end user.
The answers live in the manifest. The skills read them with `profile show --json`.
"""
import os

from harness import manifest
from harness.util import HarnessError, write_text

QUESTIONS = [
    ("architecture", "Architecture in one sentence (for example: SPA + REST API + Postgres)"),
    ("languages", "Languages, comma separated (for example: typescript, python)"),
    ("purpose", "Purpose in one sentence: what the software does"),
    ("end_user", "End user in one sentence: who uses it and what they lose when it fails"),
]

LANGUAGE_PATTERNS = {
    "python": "**/*.py", "typescript": "**/*.{ts,tsx}", "javascript": "**/*.{js,jsx,mjs}",
    "php": "**/*.php", "go": "**/*.go", "rust": "**/*.rs", "java": "**/*.java",
    "kotlin": "**/*.kt", "c": "**/*.{c,h}", "cpp": "**/*.{cpp,cc,hpp,h}", "c++": "**/*.{cpp,cc,hpp,h}",
    "csharp": "**/*.cs", "c#": "**/*.cs", "ruby": "**/*.rb", "swift": "**/*.swift",
    "shell": "**/*.sh", "bash": "**/*.sh", "sql": "**/*.sql",
}


def load(root):
    data = manifest.load(root)
    if data is None:
        raise HarnessError("not initialised. Run `python3 -m harness init`.")
    return data, data.setdefault("profile", {"architecture": "", "languages": [], "purpose": "", "end_user": ""})


def set_values(root, pairs):
    data, profile = load(root)
    for key, value in pairs:
        if key not in dict(QUESTIONS):
            raise HarnessError("unknown profile key %s. Use one of %s." % (key, ", ".join(k for k, _ in QUESTIONS)))
        if key == "languages":
            profile[key] = [v.strip().lower() for v in value.split(",") if v.strip()]
        else:
            profile[key] = value.strip()
    manifest.save(root, data)
    return profile


def ask(root, reader=input):
    data, profile = load(root)
    for key, question in QUESTIONS:
        current = profile.get(key)
        shown = ", ".join(current) if isinstance(current, list) else (current or "")
        answer = reader("%s%s: " % (question, (" [%s]" % shown) if shown else ""))
        if not answer.strip():
            continue
        set_values(root, [(key, answer)])
        data, profile = load(root)
    return profile


def show(root):
    _, profile = load(root)
    return profile


def profile_text(profile):
    lines = []
    for key, _ in QUESTIONS:
        v = profile.get(key)
        v = ", ".join(v) if isinstance(v, list) else v
        lines.append("  %-13s %s" % (key, v or "(empty)"))
    return "\n".join(lines)


def code_patterns(profile):
    out = []
    for lang in profile.get("languages") or []:
        p = LANGUAGE_PATTERNS.get(lang)
        if p and p not in out:
            out.append(p)
    return out


# ---------------------------------------------------------------- generated skills

def _skill(name, description, body):
    return "---\nname: %s\ndescription: %s\n---\n\n%s" % (name, description, body)


def generate_skills(root):
    _, profile = load(root)
    arch = profile.get("architecture") or "(no architecture declared)"
    langs = ", ".join(profile.get("languages") or []) or "(no language declared)"
    purpose = profile.get("purpose") or "(no purpose declared)"
    user = profile.get("end_user") or "(no end user declared)"
    skills = {
        "project-map": _skill(
            "project-map",
            "Reads the architecture of this project before a change. Use when a task touches more than one component, or when the agent must name where a piece of logic lives.",
            "# Project map\n\nThe profile declares: **%s**. Languages: %s.\n\n"
            "1. Run `python3 -m harness profile show`. If the architecture changed, tell the user. Do not edit the profile.\n"
            "2. Run the `architecture-reader` skill with the component that the task names.\n"
            "3. Name every file that the change touches, with `file:line`. Count the call sites. Do not read them from memory.\n"
            "4. If a call site lives in a dependency, say so. A grep that returns nothing does not close the question.\n"
            % (arch, langs)),
        "project-user-impact": _skill(
            "project-user-impact",
            "States what the end user loses when a change fails. Use before a task with eye RUN or GLANCE closes, and in every review.",
            "# Project user impact\n\nPurpose: **%s**. End user: **%s**.\n\n"
            "1. Run the `end-user-impact` skill with the task id.\n"
            "2. Write one sentence: what the user cannot do if this change is wrong.\n"
            "3. Name the check that a person must run to see the change. A green build is not a working feature.\n"
            "4. Put that sentence in the task file under `## Done when`.\n"
            % (purpose, user)),
        "project-conventions": _skill(
            "project-conventions",
            "The conventions of this project: languages, package policy, writing rules. Use before the first edit of a session.",
            "# Project conventions\n\nLanguages: %s.\n\n"
            "1. Read the rules file that `python3 -m harness doctor --json` names as `rules_path`.\n"
            "2. Follow the Glossary. One word, one meaning.\n"
            "3. Add no dependency without a measured need and the user's approval.\n"
            "4. Run the test command of the repository before you report a change as done.\n"
            % langs),
    }
    written = []
    for name, text in skills.items():
        p = os.path.join(root, ".claude", "skills", name, "SKILL.md")
        write_text(p, text)
        written.append(os.path.relpath(p, root))
    return written
