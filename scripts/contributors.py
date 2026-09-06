#!/usr/bin/env python3
"""Write the contributor list of README.md from the GitHub API.

The list sits between two markers. This script replaces the lines between them, and
it changes nothing else. It uses the Python standard library only.

    python3 scripts/contributors.py            write README.md
    python3 scripts/contributors.py --check    exit 1 when the list is stale

A person runs this, once a week, and reads the diff before the commit. No workflow
runs it. A job that writes to the default branch needs a token with write rights, and
it commits with no human in the path. That is a place to hide a change. The list of
contributors changes a few times a year, so a weekly command costs less than the
surface that automation opens.

The script reads TWO endpoints and joins the answers.

`/contributors` aggregates the whole history, and GitHub caches it. Measured on
2026-09-06: it named 1 person while the repository page named 3, and a contributor
who landed 40 minutes earlier was missing. A cache alone loses a new name.

`/commits` resolves the author of each recent commit to an account, and it is fresh.
It carries the last page only, so it loses an old name. Neither endpoint answers
alone. The union of the two answers both questions.

The script writes names and pictures, and never commit counts. A count changes on
every push, and that costs one commit per push. A name changes when a new person
lands a first patch.

A co-author trailer names an address, and not an account. GitHub resolves those
addresses on its own page, and the API does not. Measured: a search for
`noreply@anthropic.com` returned 0 accounts. This script never guesses a login from
an address, so a co-author appears here only when that person also authors a commit.
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
CONTRIBUTORS_URL = "https://api.github.com/repos/%s/contributors?per_page=100"
COMMITS_URL = "https://api.github.com/repos/%s/commits?per_page=100"
TIMEOUT_S = 20
AVATAR_PX = 96
PER_ROW = 6


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


def get_json(url, token=None):
    """Return the rows of one GET. Raise when the answer is not a list of rows.

    GitHub answers a list of people on success. It answers an OBJECT to carry a
    message, such as a rate limit. A caller that iterates an object reads its keys as
    rows, and a key is a string with no `get`. Measured on 2026-09-06: a rate-limit
    body raised `AttributeError` out of `main`, and the script died with a traceback.

    A `ValueError` here lands in the caller that already reports no answer, so the
    script says what happened and leaves README.md alone.
    """
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json", "User-Agent": "harness-contributors"})
    if token:
        req.add_header("Authorization", "Bearer %s" % token)
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if not isinstance(data, list):
        message = data.get("message") if isinstance(data, dict) else ""
        raise ValueError("%s answered no list of people (%s)"
                         % (url, message or type(data).__name__))
    return data


def is_person(login, kind):
    """Return True for a human account. A bot never lands in a thanks list."""
    return bool(login) and kind != "Bot" and not login.endswith("[bot]")


def people(slug, token=None):
    """Return (login, avatar) per person, most commits first.

    Read the cached aggregate first, then the fresh page of commits. A name from
    either endpoint counts. A rank from the aggregate wins, because it reads the
    whole history.
    """
    found = {}
    order = {}
    for row in get_json(CONTRIBUTORS_URL % slug, token):
        login = row.get("login") or ""
        if is_person(login, row.get("type")):
            found[login] = row.get("avatar_url") or ""
            order[login] = -(row.get("contributions") or 0)
    rank = len(order)
    for row in get_json(COMMITS_URL % slug, token):
        author = row.get("author") or {}
        login = author.get("login") or ""
        if not is_person(login, author.get("type")):
            continue
        if login not in found:
            found[login] = author.get("avatar_url") or ""
            rank += 1
            order[login] = rank  # after every ranked name, and before the next new one
    return sorted(((login, found[login]) for login in found),
                  key=lambda p: (order[p[0]], p[0].lower()))


def avatar_src(login, avatar):
    """Return the picture url at the size this list uses.

    The API url already carries a query, so the size joins it with `&`. The
    `github.com/<login>.png` form is the fallback when a row carries no picture.
    """
    if not avatar:
        return "https://github.com/%s.png?size=%d" % (login, AVATAR_PX)
    joiner = "&" if "?" in avatar else "?"
    return "%s%ss=%d" % (avatar, joiner, AVATAR_PX)


def cell(login, avatar):
    """Return one table cell: a picture above a name, both inside one link.

    The `alt` stays empty on purpose. The link already holds the login as text, so a
    screen reader reads the name from the link. An `alt` that repeats the login makes
    the reader say the name twice. WAI names this case "an image and text in the same
    link", and it asks for a null `alt` there.
    """
    return ('<td align="center"><a href="https://github.com/%s">'
            '<img src="%s" width="%d" alt=""><br><sub><b>%s</b></sub></a></td>'
            % (login, avatar_src(login, avatar), AVATAR_PX, login))


def block(persons):
    """Return the table. `main` never calls this with an empty list."""
    rows = []
    for i in range(0, len(persons), PER_ROW):
        cells = "".join(cell(login, avatar) for login, avatar in persons[i:i + PER_ROW])
        rows.append("  <tr>%s</tr>" % cells)
    return "<table>\n%s\n</table>" % "\n".join(rows)


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
    slug = repo_slug()
    # Name the urls, and never the slug. A reader who debugs a rate limit or an auth
    # error needs the address that answered, not the name of the repository.
    urls = "%s and %s" % (CONTRIBUTORS_URL % slug, COMMITS_URL % slug)
    try:
        persons = people(slug, os.environ.get("GITHUB_TOKEN"))
    except (urllib.error.URLError, OSError, ValueError) as exc:
        # No answer is not an empty list. A wrong list removes a name that a person earned.
        print("contributors: %s gave no answer (%s). README.md is unchanged." % (urls, exc))
        return 0
    if not persons:
        # An empty list is not an answer either. Both endpoints answer with an empty
        # array while GitHub counts a repository, and every name would go.
        print("contributors: %s listed no person. README.md is unchanged, because an "
              "empty list is not a measurement." % urls)
        return 0
    with open(README, encoding="utf-8") as fh:
        text = fh.read()
    new = rewrite(text, block(persons))
    if new == text:
        print("contributors: %d name(s), and the list is current." % len(persons))
        return 0
    if check:
        print("contributors: README.md is stale. It names %d person(s), and the API names %d. "
              "Run `python3 scripts/contributors.py`." % (text.count("<sub><b>"), len(persons)))
        return 1
    with open(README, "w", encoding="utf-8") as fh:
        fh.write(new)
    print("contributors: wrote %d name(s) to README.md." % len(persons))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
