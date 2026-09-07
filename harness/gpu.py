"""Can this host run the search index on a GPU? Measure it, and never guess.

The harness ships the GPU path already. `infra/rag/docker-compose.gpu.yml` holds the
build target and the device reservation, and `python3 -m harness stack up --gpu`
merges it. Nothing measured the host, so an adopter runs the CPU image and never
learns that the machine holds a card. The cost of the CPU path is measured: `qmd
embed` took 60749 ms on 2026-09-05, and `qmd` prints "no GPU acceleration, running on
CPU (slow)" on every run.

This module answers `yes`, `no`, or `unknown`, and it names the reason. `unknown` is
the answer when a step does not answer. A default value must never look like a
measurement (design law 7), so a stopped daemon reads as `unknown` and never as `no`.

`nvidia-smi` on the host does not prove that a container reaches the card. That is
design law 3: a path that still exists does not prove that the path is correct. Only
`docker run --gpus all <image> nvidia-smi -L` proves it, and only that step returns
`yes`.

The container step costs seconds, so it runs on demand. `init` and `python3 -m
harness gpu` run it. `doctor` runs the three host steps and reads the cached answer of
the last deep run.
"""
import json
import os
import sys

from harness import env, stack
from harness.util import HarnessError, now_iso, read_text, write_text

PATH = os.path.join(".harness", "gpu.json")

# `nvidia-smi` answers in milliseconds on a sound driver. `docker info` took 2.6 s on
# this host. A container start costs seconds. Each cap catches a hang, and no cap is a
# budget.
SMI_TIMEOUT = 20
INFO_TIMEOUT = 30
RUN_TIMEOUT = 120

# The macOS answer. No Mac ran this check, so the text names itself as a claim.
MACOS = ("macOS. Docker Desktop runs the containers in a Linux virtual machine, and "
         "that machine does not reach the Apple GPU. No Mac measured this yet.")


def image(root):
    """The tag of the CPU image of the `rag` stack, as the compose file builds it."""
    project = env.read(root).get("HARNESS_PROJECT") or env.derive(root)["HARNESS_PROJECT"]
    return "%s-rag:cpu" % project


def _last(out):
    lines = [l.strip() for l in (out or "").splitlines() if l.strip()]
    return lines[-1] if lines else "no output"


def card_name(text):
    """The card of the first `GPU n:` line of `nvidia-smi -L`. None when there is none."""
    for line in (text or "").splitlines():
        line = line.strip()
        if not line.startswith("GPU ") or ":" not in line:
            continue
        name = line.split(":", 1)[1].strip().split(" (UUID")[0].strip()
        if name:
            return name
    return None


def probe(root, deep=False):
    """Measure the host. Stop at the first `no`. Return the report.

    `deep` adds the container step. Without it the best answer is `unknown`: the host
    looks ready and nothing proved that a container reaches the card.
    """
    report = {"answer": "unknown", "reason": "", "steps": [], "deep": bool(deep),
              "platform": sys.platform, "card": "", "runtimes": [], "image": image(root),
              "proved_by_container": False, "measured_at": now_iso()}

    def stop(name, answer, reason):
        report["steps"].append({"step": name, "answer": answer, "reason": reason})
        report["answer"], report["reason"] = answer, reason
        return report

    def passed(name, reason):
        report["steps"].append({"step": name, "answer": "yes", "reason": reason})

    if sys.platform == "darwin":
        return stop("platform", "no", MACOS)
    passed("platform", "%s passes a GPU to a container" % sys.platform)

    code, out = stack.sh(["nvidia-smi", "-L"], timeout=SMI_TIMEOUT)
    if code == 127:
        return stop("nvidia-smi", "no", "nvidia-smi is not on the PATH. This host runs no NVIDIA driver.")
    if code == 124:
        return stop("nvidia-smi", "unknown", "nvidia-smi did not answer in %ss." % SMI_TIMEOUT)
    if code != 0:
        return stop("nvidia-smi", "no", "nvidia-smi exited %d: %s" % (code, _last(out)))
    card = card_name(out)
    if not card:
        return stop("nvidia-smi", "no", "nvidia-smi names no GPU: %s" % _last(out))
    report["card"] = card
    passed("nvidia-smi", "the driver names %s" % card)

    ok, reason = stack.probe()
    if not ok:
        return stop("docker", "unknown", "docker does not answer, so no container can be measured. %s" % reason)
    passed("docker", "the daemon answers")

    code, out = stack.sh(["docker", "info", "--format", "{{range $k, $v := .Runtimes}}{{$k}}\n{{end}}"],
                         timeout=INFO_TIMEOUT)
    if code != 0:
        return stop("docker-runtimes", "unknown", "docker info did not answer: %s" % _last(out))
    report["runtimes"] = sorted(l.strip() for l in out.splitlines() if l.strip())
    if "nvidia" not in report["runtimes"]:
        have = ", ".join(report["runtimes"]) or "none"
        return stop("docker-runtimes", "no",
                    "docker registers no `nvidia` runtime (it has: %s). Install nvidia-container-toolkit, "
                    "then run `sudo nvidia-ctk runtime configure --runtime=docker`." % have)
    passed("docker-runtimes", "docker registers the nvidia runtime")

    if not deep:
        return stop("container", "unknown",
                    "the host looks ready and no container proved it. Run `python3 -m harness gpu`.")

    tag = report["image"]
    code, out = stack.sh(["docker", "image", "inspect", tag, "--format", "{{.Id}}"], timeout=INFO_TIMEOUT)
    if code != 0:
        return stop("container", "unknown",
                    "the image %s does not exist on this host, so no container can prove the path. "
                    "Run `python3 -m harness stack up`, then `python3 -m harness gpu`." % tag)
    code, out = stack.sh(["docker", "run", "--rm", "--gpus", "all", tag, "nvidia-smi", "-L"],
                         timeout=RUN_TIMEOUT)
    if code == 124:
        return stop("container", "unknown", "the container did not answer in %ss." % RUN_TIMEOUT)
    if code != 0:
        return stop("container", "no", "a container with --gpus all cannot reach the card: %s" % _last(out))
    inside = card_name(out)
    if not inside:
        return stop("container", "no", "the container ran and nvidia-smi names no GPU inside it: %s" % _last(out))
    report["card"] = inside
    report["proved_by_container"] = True
    return stop("container", "yes", "a container reached %s with --gpus all." % inside)


def path(root):
    return os.path.join(root, PATH)


def save(root, report):
    """Write the answer of a deep run. `doctor` reads it and starts no container."""
    write_text(path(root), json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    return report


def load(root):
    """The cached report of the last deep run, or None."""
    p = path(root)
    if not os.path.exists(p):
        return None
    try:
        data = json.loads(read_text(p))
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def measure(root, deep=True):
    """Probe, and cache the answer when the run measured one.

    An `unknown` answer never reaches the cache. `unknown` means "this run measured
    nothing", and a run that measured nothing must not erase a run that measured
    something. Design law 7 again: a default value must never look like a measurement.
    A stopped daemon then leaves the proof of the last deep run in place, and `doctor`
    still names the date of that run.
    """
    report = probe(root, deep=deep)
    if deep and report["answer"] in ("yes", "no"):
        save(root, report)
    return report


def cpu_image_runs(root):
    """The services of the `rag` stack that run the CPU image. Empty on any doubt."""
    tag = image(root)
    try:
        report = stack.status(root, "rag")
    except (HarnessError, OSError):
        return []
    return sorted(s["service"] for s in report.get("services") or []
                  if s.get("state") == "running" and s.get("image") == tag)


def note(root, report=None):
    """One line for `doctor`, or "" when there is nothing to act on.

    A canary that sings on every run is not read. The note appears when the user can
    do something: switch a running CPU stack to the GPU, or prove a ready host.
    """
    report = report or probe(root, deep=False)
    cached = load(root)
    if cached and cached.get("answer") == "yes" and report["answer"] != "no":
        on_cpu = cpu_image_runs(root)
        if on_cpu:
            return ("GPU: yes (%s), and the rag stack runs the CPU image on %s. "
                    "Run `python3 -m harness stack up --gpu`." % (cached.get("card") or "this host", ", ".join(on_cpu)))
        return "GPU: yes (%s), measured on %s." % (cached.get("card") or "this host", cached.get("measured_at") or "an earlier run")
    if report["answer"] == "unknown" and report["card"]:
        return "GPU: the driver names %s and no container proved the path. Run `python3 -m harness gpu`." % report["card"]
    return ""


def text(report):
    lines = ["GPU: %s — %s" % (report["answer"], report["reason"])]
    for s in report["steps"]:
        lines.append("  [%s] %-15s %s" % ({"yes": "+", "no": "X", "unknown": "?"}[s["answer"]], s["step"], s["reason"]))
    lines.append("  image %s, measured %s" % (report["image"], report["measured_at"]))
    if report["answer"] == "yes":
        lines.append("  Start the stack on the GPU: `python3 -m harness stack up --gpu`.")
    return "\n".join(lines)


def init_line(report):
    """The one line that `init` prints. "" when the host answers no on a plain reason."""
    if report["answer"] == "yes":
        return "GPU: yes (%s). Run `python3 -m harness stack up --gpu` to use it." % (report["card"] or "this host")
    if report["answer"] == "unknown":
        return "GPU: unknown. %s" % report["reason"]
    return "GPU: no. %s" % report["reason"]
