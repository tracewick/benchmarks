#!/usr/bin/env bash
# Start exactly one spool reader: drain | agent | off.
# Usage: READER=agent ./scripts/ensure-reader.sh
#        ./scripts/ensure-reader.sh agent
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

COMPOSE=${COMPOSE:-docker compose}
READER=${1:-${READER:-drain}}

case "$READER" in
  drain|agent|off) ;;
  *)
    echo "ensure-reader: READER must be drain|agent|off (got: $READER)" >&2
    exit 2
    ;;
esac

echo "==> Reader mode: $READER"

case "$READER" in
  drain)
    $COMPOSE --profile agent stop app-agent 2>/dev/null || true
    $COMPOSE up -d --no-deps app-drain
    ;;
  agent)
    $COMPOSE stop app-drain 2>/dev/null || true
    $COMPOSE --profile agent build app-agent
    $COMPOSE --profile agent up -d --no-deps app-agent
    # Wait for metrics (agent is up) or at least container running.
    for i in $(seq 1 30); do
      if curl -sf http://127.0.0.1:${AGENT_METRICS_PORT:-9090}/metrics >/dev/null 2>&1; then
        break
      fi
      sleep 1
    done
    ;;
  off)
    $COMPOSE stop app-drain 2>/dev/null || true
    $COMPOSE --profile agent stop app-agent 2>/dev/null || true
    ;;
esac

$COMPOSE ps app-drain app-agent 2>/dev/null || $COMPOSE --profile agent ps app-drain app-agent 2>/dev/null || true
