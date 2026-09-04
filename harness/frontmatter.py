"""Read and write the front matter of a markdown file.

The format is a flat subset of YAML: `key: value`, and lists as `- item` lines or
as `[a, b]`. Nesting is not supported, and the files do not need it.
"""
import re

_FM = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n?", re.S)
_KV = re.compile(r"^([A-Za-z0-9_-]+):\s*(.*)$")
_ITEM = re.compile(r"^\s+-\s+(.*)$")


def _unquote(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def parse(text):
    """Return (fields, body). Fields is an ordered dict. Missing front matter gives {}."""
    m = _FM.match(text)
    if not m:
        return {}, text
    fields = {}
    key = None
    for line in m.group(1).splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        item = _ITEM.match(line)
        if item and key is not None:
            if not isinstance(fields[key], list):
                fields[key] = [] if fields[key] in ("", None) else [fields[key]]
            fields[key].append(_unquote(item.group(1)))
            continue
        kv = _KV.match(line)
        if not kv:
            continue
        key = kv.group(1)
        raw = kv.group(2).split(" #", 1)[0].strip()
        if raw.startswith("[") and raw.endswith("]"):
            inner = raw[1:-1].strip()
            fields[key] = [_unquote(x) for x in inner.split(",") if x.strip()] if inner else []
        else:
            fields[key] = _unquote(raw)
    return fields, text[m.end():]


def dump(fields, body=""):
    """Render fields and body as one markdown document."""
    lines = ["---"]
    for key, value in fields.items():
        if isinstance(value, list):
            if value:
                lines.append("%s:" % key)
                lines.extend("  - %s" % v for v in value)
            else:
                lines.append("%s: []" % key)
        elif value is None or value == "":
            continue
        else:
            text = str(value)
            if ":" in text or text.startswith(("[", "{", "#")):
                text = '"%s"' % text.replace('"', '\\"')
            lines.append("%s: %s" % (key, text))
    lines.append("---")
    out = "\n".join(lines) + "\n"
    if body:
        out += ("\n" if not body.startswith("\n") else "") + body
    return out


def read(path):
    with open(path, encoding="utf-8") as fh:
        return parse(fh.read())


def as_list(value):
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return [str(v) for v in value if str(v).strip()]
    return [str(value)]
