# syntax=docker/dockerfile:1.7
#
# The search index image. Two targets: `cpu` (default, portable) and `gpu` (CUDA).
#
# Bases are pinned by digest, not by tag. A tag can be repainted. A digest cannot.
# Read a digest back with: docker image inspect <image> --format '{{index .RepoDigests 0}}'
#   oven/bun:1.3.8-slim                  sha256:68fc2eac...2e41   (2026-09-02)
#   nvidia/cuda:13.0.1-base-ubuntu22.04  sha256:64462f4f...0ca4   (amd64, 2026-09-02)
#
# The only third-party code of the harness lives here: @tobilu/qmd, from the
# lockfile, with --ignore-scripts. That blocks 5 postinstall scripts. qmd runs
# without them. The companion agent is Python standard library.

FROM oven/bun@sha256:68fc2eac7f5dcfc2f69a81d1db02786ab08772eda2e4404eae785c038f8d2e41 AS deps
WORKDIR /opt/qmd
COPY package.json bun.lock ./
RUN bun install --frozen-lockfile --ignore-scripts --production \
 && G=node_modules/@node-llama-cpp \
 && rm -rf $G/linux-x64-cuda-ext $G/linux-x64-vulkan $G/linux-arm64 $G/linux-armv7l \
 && rm -rf /root/.bun/install/cache

FROM oven/bun@sha256:68fc2eac7f5dcfc2f69a81d1db02786ab08772eda2e4404eae785c038f8d2e41 AS cpu
RUN apt-get update && apt-get install -y --no-install-recommends python3 \
 && rm -rf /var/lib/apt/lists/*
RUN --mount=type=bind,from=deps,source=/opt/qmd,target=/mnt/qmd \
    cp -a /mnt/qmd /opt/qmd && rm -rf /opt/qmd/node_modules/@node-llama-cpp/linux-x64-cuda
ENV PATH="/opt/qmd/node_modules/.bin:$PATH" XDG_CACHE_HOME=/data/cache XDG_CONFIG_HOME=/data/config QMD_LLAMA_GPU=false
WORKDIR /data
CMD ["qmd","--help"]

FROM nvidia/cuda@sha256:64462f4f1ce658e6512c06b70997da2883a03865b87b80a47e3680d7bf120ca4 AS gpu
RUN apt-get update && apt-get install -y --no-install-recommends libcublas-13-0 python3 \
 && rm -rf /var/lib/apt/lists/*
COPY --from=oven/bun@sha256:68fc2eac7f5dcfc2f69a81d1db02786ab08772eda2e4404eae785c038f8d2e41 /usr/local/bin/bun /usr/local/bin/bun
COPY --from=oven/bun@sha256:68fc2eac7f5dcfc2f69a81d1db02786ab08772eda2e4404eae785c038f8d2e41 /usr/local/bun-node-fallback-bin /usr/local/bun-node-fallback-bin
RUN --mount=type=bind,from=deps,source=/opt/qmd,target=/mnt/qmd cp -a /mnt/qmd /opt/qmd
ENV PATH="/opt/qmd/node_modules/.bin:/usr/local/bun-node-fallback-bin:$PATH" XDG_CACHE_HOME=/data/cache XDG_CONFIG_HOME=/data/config QMD_LLAMA_GPU=cuda
WORKDIR /data
CMD ["qmd","--help"]
