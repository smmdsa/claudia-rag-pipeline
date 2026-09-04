#!/usr/bin/env bash
# Start the search index stack with this machine's paths.
# Usage: ./up.sh [--gpu] [compose args...]
#   ./up.sh              build and start (cpu)
#   ./up.sh --gpu        build and start with the cuda target
#   ./up.sh down         stop
#   ./up.sh logs -f rag-agent
#
# Every host path comes from .harness/env.local. This script derives that file when
# it is missing. It asks for nothing. It checks the ports before `up`.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
ENV_FILE="$REPO_ROOT/.harness/env.local"

if [ ! -f "$ENV_FILE" ]; then
  (cd "$REPO_ROOT" && python3 -m harness env >/dev/null)
fi
set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
set +a

# Docker creates a missing bind source as root. Create the memory directory as the user first.
mkdir -p "$HARNESS_MEMORY_DIR"

FILES=(-f "$HERE/docker-compose.yml")
if [ "${1:-}" = "--gpu" ]; then FILES+=(-f "$HERE/docker-compose.gpu.yml"); shift; fi
ARGS=("$@")
if [ ${#ARGS[@]} -eq 0 ]; then ARGS=(up -d --build); fi

if [ "${ARGS[0]}" = "up" ]; then
  if ! (cd "$REPO_ROOT" && HARNESS_BOARD_PORT=0 python3 -m harness ports); then
    echo "up.sh: a port is taken. Override it in the environment and run again." >&2
    exit 1
  fi
fi

exec docker compose --env-file "$ENV_FILE" "${FILES[@]}" "${ARGS[@]}"
