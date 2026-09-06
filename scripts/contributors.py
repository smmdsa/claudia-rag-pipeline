#!/usr/bin/env python3
"""Write the contributor list of README.md from the GitHub API.

The list sits between two markers. This script replaces the lines between them, and
it changes nothing else. It uses the Python standard library only.

    python3 scripts/contributors.py            write README.md
    python3 scripts/contributors.py --check    exit 1 when the list is stale

The script writes names and never commit counts. A count changes on every push, and
that costs one commit per push. A name changes when a new person lands a patch.

The GitHub API counts commits on the default branch, so a name appears after the
first merge, and never while the pull request is open. The script skips every bot.
"""
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

README = "README.md"
START = "<!-- contributors:start -->"
END = "<!-- contributors:end -->"
API = "https://api.github.com/repos/%s/contributors?per_page=100"
TIMEOUT_S = 20


def repo_slug():
    """Return `owner/name`. The workflow sets GITHUB_REPOSITORY. Git answers locally."""
    slug = os.environ.get("GITHUB_REPOSITORY")
    if slug:
        return slug
    out = subprocess.run(["git", "remote", "get-url", "origin"],
                         capture_output=True, text=True).stdout.strip()
    found = re.search(r"[:/]([^/:]+/[^/]+?)(?:\.git)?$", out)
    if not found:
        raise SystemExit("contributors: this repository names no GitHub remote. The script reads "
                         "the remote to find the owner. Set GITHUB_REPOSITORY, or add an origin remote.")
    return found.group(1)


def contributors(url, token=None):
    """Return one login per person, most commits first. Skip every bot account."""
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json", "User-Agent": "harness-contributors"})
    if token:
        req.add_header("Authorization", "Bearer %s" % token)
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
        rows = json.loads(resp.read().decode("utf-8"))
    people = [(r.get("login") or "", r.get("contributions") or 0) for r in rows
              if r.get("type") != "Bot" and not (r.get("login") or "").endswith("[bot]")]
    people = [p for p in people if p[0]]
    people.sort(key=lambda p: (-p[1], p[0].lower()))
    return [login for login, _ in people]


def block(logins):
    """Return the markdown of the list. `main` never calls this with an empty list."""
    return " · ".join("[@%s](https://github.com/%s)" % (name, name) for name in logins)


def rewrite(text, body):
    """Put `body` between the two markers. Report an error when a marker is missing."""
    start = text.find(START)
    end = text.find(END)
    if start < 0 or end < 0 or end < start:
        raise SystemExit("contributors: README.md holds no contributor markers, so the script has "
                         "no place to write. Add the lines %s and %s." % (START, END))
    return text[:start + len(START)] + "\n" + body + "\n" + text[end:]


def main(argv):
    check = "--check" in argv
    url = API % repo_slug()
    try:
        logins = contributors(url, os.environ.get("GITHUB_TOKEN"))
    except (urllib.error.URLError, OSError, ValueError) as exc:
        # No answer is not an empty list. A wrong list removes a name that a person earned.
        print("contributors: %s gave no answer (%s). README.md is unchanged." % (url, exc))
        return 0
    if not logins:
        # An empty list is not an answer either. The API answers with an empty array on
        # a repository that it did not finish counting, and every name would go.
        print("contributors: %s listed no person. README.md is unchanged, because an "
              "empty list is not a measurement." % url)
        return 0
    with open(README, encoding="utf-8") as fh:
        text = fh.read()
    new = rewrite(text, block(logins))
    if new == text:
        print("contributors: %d name(s), and the list is current." % len(logins))
        return 0
    if check:
        print("contributors: README.md is stale. Run `python3 scripts/contributors.py`.")
        return 1
    with open(README, "w", encoding="utf-8") as fh:
        fh.write(new)
    print("contributors: wrote %d name(s) to README.md." % len(logins))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
