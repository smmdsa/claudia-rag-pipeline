"""The machine environment file. Every value is derived. Nothing is asked.

A config file of absolute paths drifts. A derivation cannot. Source A shipped
`.mcp.json` with a `wsl` wrapper and collections that pointed at an abandoned tree.
Both were paths wired to one machine. `.harness/env.local` is git-ignored.
"""
import os
import re

from harness.ports import DEFAULTS, port_for
from harness.util import now_iso, read_text, write_text

PATH = os.path.join(".harness", "env.local")


def derive(root):
    root = os.path.realpath(root)
    slug = root.replace("/", "-")
    claude_home = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
    values = {
        "HARNESS_REPO_ROOT": root,
        "HARNESS_REPO_SLUG": slug,
        "HARNESS_CLAUDE_HOME": claude_home,
        "HARNESS_MEMORY_DIR": os.path.join(claude_home, "projects", slug, "memory"),
        "HARNESS_PROJECT": re.sub(r"[^a-z0-9]+", "-", os.path.basename(root).lower()).strip("-") or "project",
    }
    for var in DEFAULTS:
        # A pure derivation: the shell or the default, and never the file that this
        # writes. A writer that reads its own output cannot reset a wrong value. The
        # user overrides a port in the shell, `env` writes it here, and every reader
        # then takes it from this file.
        raw = os.environ.get(var)
        values[var] = raw if raw and raw.isdigit() else str(DEFAULTS[var][0])
    values["HARNESS_ENV_AT"] = now_iso()
    return values


def write(root):
    values = derive(root)
    lines = ["# Derived by `python3 -m harness env` on %s. Git ignores this file." % values["HARNESS_ENV_AT"],
             "# Every value comes from this machine. To regenerate it, run the command again."]
    for k, v in values.items():
        lines.append('%s="%s"' % (k, v))
    write_text(os.path.join(root, PATH), "\n".join(lines) + "\n")
    return values


def read(root):
    p = os.path.join(root, PATH)
    if not os.path.exists(p):
        return {}
    out = {}
    for line in read_text(p).splitlines():
        m = re.match(r'^(HARNESS_\w+)="(.*)"\s*$', line.strip())
        if m:
            out[m.group(1)] = m.group(2)
    return out


def env_text(values):
    width = max(len(k) for k in values)
    return "\n".join("  %-*s %s" % (width, k, v) for k, v in values.items())
