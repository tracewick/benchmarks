#!/usr/bin/env bash
# Sequential short soaks across runtimes with go-agent (leak / RSS check).
# Usage: DURATION=6h RATE=10 WORK_STACK_DEPTH=48 ./scripts/run-soak-matrix.sh
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

DURATION=${DURATION:-6h}
RATE=${RATE:-10}
STACK_DEPTH=${WORK_STACK_DEPTH:-48}
SAMPLE_RATE=${TRACEWICK_SAMPLE_RATE:-0.1}
STATS_INTERVAL=${STATS_INTERVAL:-60}
READER=${READER:-agent}
REPORTS_DIR=${REPORTS_DIR:-reports/_local}

# Modest pools — soak is about growth, not max RPS.
FPM_CHILDREN=${PHP_FPM_MAX_CHILDREN:-8}
RR_WORKERS=${RR_NUM_WORKERS:-8}
SWOOLE_WORKERS=${SWOOLE_WORKER_NUM:-8}

RUNTIMES=${RUNTIMES:-"fpm rr swoole"}

mkdir -p "$REPORTS_DIR"
manifest="$REPORTS_DIR/soak-matrix-$(date -u +%Y%m%dT%H%M%SZ).log"
echo "soak-matrix start $(date -u +%Y-%m-%dT%H:%M:%SZ) DURATION=$DURATION READER=$READER DEPTH=$STACK_DEPTH RUNTIMES=$RUNTIMES" | tee "$manifest"

chmod +x "$ROOT/scripts/run-soak.sh"

for rt in $RUNTIMES; do
  echo "" | tee -a "$manifest"
  echo "==== RUNTIME=$rt $(date -u +%Y-%m-%dT%H:%M:%SZ) ====" | tee -a "$manifest"
  case "$rt" in
    fpm) base=http://127.0.0.1:8080 ;;
    rr) base=http://127.0.0.1:8082 ;;
    swoole) base=http://127.0.0.1:8083 ;;
    *) echo "unknown runtime $rt" >&2; exit 2 ;;
  esac
  RATE="$RATE" DURATION="$DURATION" READER="$READER" RUNTIME="$rt" \
    BASE_URL="$base" WORK_STACK_DEPTH="$STACK_DEPTH" \
    TRACEWICK_SAMPLE_RATE="$SAMPLE_RATE" STATS_INTERVAL="$STATS_INTERVAL" \
    PHP_FPM_MAX_CHILDREN="$FPM_CHILDREN" RR_NUM_WORKERS="$RR_WORKERS" \
    SWOOLE_WORKER_NUM="$SWOOLE_WORKERS" REPORTS_DIR="$REPORTS_DIR" \
    "$ROOT/scripts/run-soak.sh" | tee -a "$manifest"
  echo "==== done RUNTIME=$rt $(date -u +%Y-%m-%dT%H:%M:%SZ) ====" | tee -a "$manifest"
done

echo "soak-matrix finished $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$manifest"
echo "Manifest: $manifest"
