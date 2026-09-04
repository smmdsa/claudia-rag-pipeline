---
id: TASK-0001
title: Start the GPU target and read nvidia-smi from inside
epic: EP-01
work: S
eye: GLANCE
owner: agent
---

# TASK-0001 — Start the GPU target and read nvidia-smi from inside

## Why

The CPU target ran on this machine on 2026-09-04: three containers healthy, the read-only mount proven with `touch` (`Read-only file system`). The GPU target built from `nvidia/cuda` by digest, and nobody read `nvidia-smi` from inside it.

## What to do

1. Run `docker compose --env-file .harness/env.local -f infra/rag/docker-compose.yml -f infra/rag/docker-compose.gpu.yml build rag`.
2. Run `docker run --rm --gpus all harness-rag-pipeline-rag:gpu nvidia-smi -L`.
3. Paste the output in this file.

Measured on 2026-09-04 19:32 -03, on this machine:

```text
GPU 0: NVIDIA GeForce RTX 3070 Ti (UUID: GPU-0a61fccd-f1a7-b6ca-84ad-b547d7bb1087)
Python 3.10.12
qmd 2.8.3 (facd35e)
```

The image is `harness-rag-pipeline-rag:gpu`. The stack itself ran on the CPU target in this session.

## Done when

- `nvidia-smi -L` prints one GPU line from inside the image.
- The user reads the line and says so.

## Not covered

This task does not measure the indexing speed of the GPU target against the CPU target.
