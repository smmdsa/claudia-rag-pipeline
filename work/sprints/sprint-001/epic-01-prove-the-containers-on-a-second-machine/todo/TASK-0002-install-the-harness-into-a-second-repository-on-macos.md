---
id: TASK-0002
title: Install the harness into a second repository on macOS
epic: EP-01
work: M
eye: RUN
owner: user
---

# TASK-0002 — Install the harness into a second repository on macOS

## Why

The product ran on one machine (WSL2, Linux 5.15, Python 3.10.12). The laws state that it runs the same on bare Linux and on macOS. Nobody measured macOS. `harness/ports.py` names `ss` first and `lsof` second; macOS has no `ss`.

## What to do

1. Clone the repository on macOS.
2. Copy `harness/` into a second repository and run `python3 -m harness init`, `doctor`, `ports`.
3. Run the test suite there.
4. Record the Python version and the test count in this file.

## Done when

- `doctor` exits 0 on macOS.
- `ports` names the holder of a taken port through `lsof`.
- The suite is green.

## Not covered

This task does not run Docker on macOS.
