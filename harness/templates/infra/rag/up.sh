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

# Check the ports of this stack only, and never refuse the stack's own ports. A stack
# that already runs holds them, and `docker compose up -d` on it is a no operation.
if [ "${ARGS[0]}" = "up" ]; then
  if ! (cd "$REPO_ROOT" && python3 -m harness stack ports --stack rag); then
    echo "up.sh: another process holds a port of this stack. Override it in the environment, or stop that process." >&2
    exit 1
  fi
fi

exec docker compose --env-file "$ENV_FILE" "${FILES[@]}" "${ARGS[@]}"
