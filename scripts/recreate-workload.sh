#!/usr/bin/env bash
# Recreate the PHP workload for the chosen runtime.
# Usage: RUNTIME=fpm|rr|swoole TRACEWICK_ENABLED=1 ... ./scripts/recreate-workload.sh
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

COMPOSE=${COMPOSE:-docker compose}
RUNTIME=${RUNTIME:-fpm}
BASE_URL=${BASE_URL:-}

case "$RUNTIME" in
  fpm|rr|swoole) ;;
  *)
    echo "recreate-workload: RUNTIME must be fpm|rr|swoole (got: $RUNTIME)" >&2
    exit 2
    ;;
esac

export TRACEWICK_ENABLED="${TRACEWICK_ENABLED:-1}"
export TRACEWICK_SAMPLE_RATE="${TRACEWICK_SAMPLE_RATE:-0.1}"
export TRACEWICK_SPOOL_MAX_FILES="${TRACEWICK_SPOOL_MAX_FILES:-500}"
export WORK_STACK_DEPTH="${WORK_STACK_DEPTH:-0}"
export WORK_BUSY_MS="${WORK_BUSY_MS:-25}"
export WORK_SLEEP_MS="${WORK_SLEEP_MS:-10}"
export PHP_FPM_MAX_CHILDREN="${PHP_FPM_MAX_CHILDREN:-4}"
export RR_NUM_WORKERS="${RR_NUM_WORKERS:-4}"
export SWOOLE_WORKER_NUM="${SWOOLE_WORKER_NUM:-4}"

case "$RUNTIME" in
  fpm)
    echo "==> Recreate app-fpm (ENABLED=$TRACEWICK_ENABLED SAMPLE=$TRACEWICK_SAMPLE_RATE DEPTH=$WORK_STACK_DEPTH)"
    $COMPOSE up -d --build --force-recreate --no-deps app-fpm
    $COMPOSE up -d --no-deps --force-recreate app-nginx
    url=${BASE_URL:-http://127.0.0.1:8080}
    ;;
  rr)
    echo "==> Recreate app-rr (ENABLED=$TRACEWICK_ENABLED SAMPLE=$TRACEWICK_SAMPLE_RATE DEPTH=$WORK_STACK_DEPTH WORKERS=$RR_NUM_WORKERS)"
    $COMPOSE up -d --build --force-recreate --no-deps app-rr
    url=${BASE_URL:-http://127.0.0.1:8082}
    ;;
  swoole)
    echo "==> Recreate app-swoole (ENABLED=$TRACEWICK_ENABLED DEPTH=$WORK_STACK_DEPTH WORKERS=$SWOOLE_WORKER_NUM ContinuousProfiler)"
    $COMPOSE up -d --build --force-recreate --no-deps app-swoole
    url=${BASE_URL:-http://127.0.0.1:8083}
    ;;
esac

for i in $(seq 1 90); do
  if curl -sf "$url/health" >/dev/null; then
    break
  fi
  sleep 1
done
curl -sf "$url/health"
echo
