#!/usr/bin/env bash
# Run baseline (profiler off) then on (sampleRate 0.1) at fixed RPS; write report draft.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

COMPOSE=${COMPOSE:-docker compose}
K6_IMAGE=${K6_IMAGE:-grafana/k6:1.8.2}
REPORTS_DIR=${REPORTS_DIR:-reports/_local}
BASE_URL=${BASE_URL:-http://127.0.0.1:8080}
RATE=${RATE:-20}
DURATION=${DURATION:-2m}
SAMPLE_RATE=${TRACEWICK_SAMPLE_RATE_ON:-0.1}
STATS_INTERVAL=${STATS_INTERVAL:-2}
STACK_DEPTH=${WORK_STACK_DEPTH:-0}
RUNTIME=${RUNTIME:-fpm} # fpm | rr | swoole
READER=${READER:-drain}

# Docker bind mounts require absolute host paths (relative → treated as volume names).
if [[ "$REPORTS_DIR" != /* ]]; then
  REPORTS_DIR="$ROOT/$REPORTS_DIR"
fi

mkdir -p "$REPORTS_DIR"
chmod a+rwx "$REPORTS_DIR" || true

stamp=$(date -u +%Y%m%dT%H%M%SZ)
run_dir="$REPORTS_DIR/overhead-$stamp"
mkdir -p "$run_dir"
chmod a+rwx "$run_dir" || true

recreate_app() {
  local enabled=$1
  local rate=$2
  chmod +x "$ROOT/scripts/recreate-workload.sh" "$ROOT/scripts/ensure-reader.sh"
  TRACEWICK_ENABLED="$enabled" TRACEWICK_SAMPLE_RATE="$rate" WORK_STACK_DEPTH="$STACK_DEPTH" \
    RUNTIME="$RUNTIME" BASE_URL="$BASE_URL" \
    PHP_FPM_MAX_CHILDREN="${PHP_FPM_MAX_CHILDREN:-4}" \
    RR_NUM_WORKERS="${RR_NUM_WORKERS:-4}" \
    SWOOLE_WORKER_NUM="${SWOOLE_WORKER_NUM:-4}" \
    "$ROOT/scripts/recreate-workload.sh" >"$run_dir/recreate-enabled-${enabled}.log"
  # Last non-empty line should be health JSON from recreate-workload.sh
  awk 'NF{line=$0} END{print line}' "$run_dir/recreate-enabled-${enabled}.log" \
    | tee "$run_dir/health-enabled-${enabled}.json"
  echo
  READER="$READER" "$ROOT/scripts/ensure-reader.sh"
}

run_one() {
  local name=$1
  local enabled=$2
  local expect=$3
  local summary="$run_dir/${name}-k6.json"
  local stats="$run_dir/${name}-fpm-stats.csv"

  recreate_app "$enabled" "$SAMPLE_RATE"

  local svc=app-fpm
  if [[ "$RUNTIME" == "rr" ]]; then svc=app-rr; fi
  if [[ "$RUNTIME" == "swoole" ]]; then svc=app-swoole; fi
  echo "==> Sampling docker stats for $svc → $stats"
  COMPOSE="$COMPOSE" "$ROOT/scripts/sample-container-stats.sh" "$svc" "$stats" "$STATS_INTERVAL" &
  local stats_pid=$!
  # Give one sample before load.
  sleep "$STATS_INTERVAL"

  echo "==> k6 overhead ($name) RATE=$RATE DURATION=$DURATION"
  docker run --rm --network host \
    -v "$ROOT/generators/k6:/scripts:ro" \
    -v "$run_dir:/out" \
    -e BASE_URL="$BASE_URL" \
    -e RATE="$RATE" \
    -e DURATION="$DURATION" \
    -e EXPECT_PROFILING="$expect" \
    "$K6_IMAGE" run /scripts/overhead.js --summary-export="/out/${name}-k6.json"

  kill "$stats_pid" 2>/dev/null || true
  wait "$stats_pid" 2>/dev/null || true
  echo "==> Finished $name (summary=$summary stats=$stats)"
}

run_one baseline 0 0
run_one on 1 1

host=$(uname -a)
sha=$(git rev-parse HEAD 2>/dev/null || echo unknown)
{
  echo "started_at_utc=$stamp"
  echo "RATE=$RATE"
  echo "DURATION=$DURATION"
  echo "TRACEWICK_SAMPLE_RATE_ON=$SAMPLE_RATE"
  echo "WORK_STACK_DEPTH=$STACK_DEPTH"
  echo "RUNTIME=$RUNTIME"
  echo "READER=$READER"
  echo "repo_sha=$sha"
  echo "host=$host"
} > "$run_dir/meta.txt"

report="$run_dir/overhead-report.md"

python3 "$ROOT/scripts/summarize-overhead.py" \
  --baseline-k6 "$run_dir/baseline-k6.json" \
  --on-k6 "$run_dir/on-k6.json" \
  --baseline-stats "$run_dir/baseline-fpm-stats.csv" \
  --on-stats "$run_dir/on-fpm-stats.csv" \
  --out "$report" \
  --repo-sha "$sha" \
  --host "$host" \
  --rate "$RATE" \
  --duration "$DURATION" \
  --sample-rate "$SAMPLE_RATE" \
  --stack-depth "$STACK_DEPTH" \
  --runtime "$RUNTIME" \
  --reader "$READER"

# Also copy to a stable path for convenience.
cp "$report" "$REPORTS_DIR/overhead-latest.md"
echo "Report: $report"
echo "Also: $REPORTS_DIR/overhead-latest.md"
cat "$report"
