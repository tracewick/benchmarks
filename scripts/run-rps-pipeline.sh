#!/usr/bin/env bash
# High-RPS pipeline hold: deeper stacks + larger FPM pool + spool timeseries.
# Defaults keep /work wall budget; WORK_STACK_DEPTH only changes frame depth.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

COMPOSE=${COMPOSE:-docker compose}
K6_IMAGE=${K6_IMAGE:-grafana/k6:1.8.2}
REPORTS_DIR=${REPORTS_DIR:-reports/_local}
BASE_URL=${BASE_URL:-http://127.0.0.1:8080}
RATE=${RATE:-500}
DURATION=${DURATION:-5m}
PATH_URI=${REQUEST_PATH:-/work}
SAMPLE_RATE=${TRACEWICK_SAMPLE_RATE:-0.1}
STACK_DEPTH=${WORK_STACK_DEPTH:-48}
FPM_CHILDREN=${PHP_FPM_MAX_CHILDREN:-32}
BUSY_MS=${WORK_BUSY_MS:-25}
SLEEP_MS=${WORK_SLEEP_MS:-10}
STATS_INTERVAL=${STATS_INTERVAL:-2}
# READER=drain|agent|off. DRAIN_MODE=off kept as alias for READER=off.
DRAIN_MODE=${DRAIN_MODE:-on}
READER=${READER:-}
RUNTIME=${RUNTIME:-fpm} # fpm | rr
if [[ -z "$READER" ]]; then
  if [[ "$DRAIN_MODE" == "off" ]]; then
    READER=off
  else
    READER=drain
  fi
fi
if [[ "$READER" == "off" ]]; then
  DRAIN_MODE=off
else
  DRAIN_MODE=on
fi
if [[ "$RUNTIME" == "rr" && "$BASE_URL" == "http://127.0.0.1:8080" ]]; then
  BASE_URL=http://127.0.0.1:8082
fi

if [[ "$REPORTS_DIR" != /* ]]; then
  REPORTS_DIR="$ROOT/$REPORTS_DIR"
fi

mkdir -p "$REPORTS_DIR"
chmod a+rwx "$REPORTS_DIR" || true
stamp=$(date -u +%Y%m%dT%H%M%SZ)
run_dir="$REPORTS_DIR/rps-pipeline-$stamp"
mkdir -p "$run_dir"
chmod a+rwx "$run_dir" || true

RR_WORKERS=${RR_NUM_WORKERS:-$FPM_CHILDREN}
echo "==> RPS pipeline RATE=$RATE DURATION=$DURATION PATH=$PATH_URI RUNTIME=$RUNTIME"
echo "    STACK_DEPTH=$STACK_DEPTH FPM_CHILDREN=$FPM_CHILDREN RR_WORKERS=$RR_WORKERS SAMPLE_RATE=$SAMPLE_RATE READER=$READER"
echo "    BUSY_MS=$BUSY_MS SLEEP_MS=$SLEEP_MS (same wall budget as overhead/soak when depth=0)"

{
  echo "started_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "RATE=$RATE"
  echo "DURATION=$DURATION"
  echo "REQUEST_PATH=$PATH_URI"
  echo "TRACEWICK_SAMPLE_RATE=$SAMPLE_RATE"
  echo "WORK_STACK_DEPTH=$STACK_DEPTH"
  echo "PHP_FPM_MAX_CHILDREN=$FPM_CHILDREN"
  echo "RR_NUM_WORKERS=$RR_WORKERS"
  echo "WORK_BUSY_MS=$BUSY_MS"
  echo "WORK_SLEEP_MS=$SLEEP_MS"
  echo "READER=$READER"
  echo "RUNTIME=$RUNTIME"
  echo "DRAIN_MODE=$DRAIN_MODE"
  echo "BASE_URL=$BASE_URL"
  echo "repo_sha=$(git rev-parse HEAD 2>/dev/null || echo unknown)"
  echo "host=$(uname -a)"
} > "$run_dir/meta.txt"

chmod +x "$ROOT/scripts/recreate-workload.sh" "$ROOT/scripts/ensure-reader.sh"
TRACEWICK_ENABLED=1 \
TRACEWICK_SAMPLE_RATE="$SAMPLE_RATE" \
WORK_STACK_DEPTH="$STACK_DEPTH" \
WORK_BUSY_MS="$BUSY_MS" \
WORK_SLEEP_MS="$SLEEP_MS" \
PHP_FPM_MAX_CHILDREN="$FPM_CHILDREN" \
RR_NUM_WORKERS="$RR_WORKERS" \
RUNTIME="$RUNTIME" \
BASE_URL="$BASE_URL" \
  "$ROOT/scripts/recreate-workload.sh" | tee "$run_dir/health.json"

READER="$READER" "$ROOT/scripts/ensure-reader.sh"

echo "ts_unix,files,bytes,claimed_or_tmp" > "$run_dir/spool-timeseries.csv"
(
  while :; do
    ts=$(date +%s)
    line=$("$ROOT/scripts/spool-snapshot.sh" || echo "0,0,0")
    echo "$ts,$line" >> "$run_dir/spool-timeseries.csv"
    sleep "$STATS_INTERVAL"
  done
) &
sampler=$!

cleanup() {
  kill "$sampler" 2>/dev/null || true
  wait "$sampler" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# Scale k6 VU pool with target rate (rough heuristic).
PRE_VUS=${PRE_VUS:-$(( RATE > 200 ? RATE / 2 : 100 ))}
MAX_VUS=${MAX_VUS:-$(( RATE > 200 ? RATE * 2 : 400 ))}
if [[ "$PRE_VUS" -lt 50 ]]; then PRE_VUS=50; fi
if [[ "$MAX_VUS" -lt "$PRE_VUS" ]]; then MAX_VUS=$PRE_VUS; fi

echo "==> k6 hold"
docker run --rm --network host \
  -v "$ROOT/generators/k6:/scripts:ro" \
  -v "$run_dir:/out" \
  -e BASE_URL="$BASE_URL" \
  -e RATE="$RATE" \
  -e DURATION="$DURATION" \
  -e REQUEST_PATH="$PATH_URI" \
  -e PRE_VUS="$PRE_VUS" \
  -e MAX_VUS="$MAX_VUS" \
  "$K6_IMAGE" run /scripts/rps.js --summary-export=/out/k6.json

cleanup
trap - EXIT INT TERM

# Restore default drain reader after off/agent runs so the stand is usable.
if [[ "$READER" != "drain" ]]; then
  READER=drain "$ROOT/scripts/ensure-reader.sh" || true
fi

sha=$(git rev-parse HEAD 2>/dev/null || echo unknown)
host=$(uname -a)
report="$run_dir/rps-pipeline-report.md"
python3 "$ROOT/scripts/summarize-rps-pipeline.py" \
  --k6 "$run_dir/k6.json" \
  --spool "$run_dir/spool-timeseries.csv" \
  --out "$report" \
  --repo-sha "$sha" \
  --host "$host" \
  --rate "$RATE" \
  --duration "$DURATION" \
  --sample-rate "$SAMPLE_RATE" \
  --stack-depth "$STACK_DEPTH" \
  --fpm-children "$FPM_CHILDREN" \
  --path "$PATH_URI" \
  --drain "$DRAIN_MODE" \
  --reader "$READER"

cp "$report" "$REPORTS_DIR/rps-pipeline-latest.md"
echo "finished_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$run_dir/meta.txt"
echo "Report: $report"
echo "Also: $REPORTS_DIR/rps-pipeline-latest.md"
