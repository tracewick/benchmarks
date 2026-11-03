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
  echo "==> Recreating app-fpm (TRACEWICK_ENABLED=$enabled SAMPLE_RATE=$rate)"
  TRACEWICK_ENABLED="$enabled" TRACEWICK_SAMPLE_RATE="$rate" \
    $COMPOSE up -d --force-recreate --no-deps app-fpm
  # nginx resolves app-fpm at start; recreate changes the container IP.
  $COMPOSE up -d --no-deps --force-recreate app-nginx
  # Drain keeps running; restart so it is not stuck on old claims after recreate.
  $COMPOSE up -d --no-deps app-drain
  for i in $(seq 1 60); do
    if curl -sf "$BASE_URL/health" >/dev/null; then
      break
    fi
    sleep 1
  done
  curl -sf "$BASE_URL/health" | tee "$run_dir/health-enabled-${enabled}.json"
  echo
}

run_one() {
  local name=$1
  local enabled=$2
  local expect=$3
  local summary="$run_dir/${name}-k6.json"
  local stats="$run_dir/${name}-fpm-stats.csv"

  recreate_app "$enabled" "$SAMPLE_RATE"

  echo "==> Sampling docker stats for app-fpm → $stats"
  COMPOSE="$COMPOSE" "$ROOT/scripts/sample-container-stats.sh" app-fpm "$stats" "$STATS_INTERVAL" &
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
  --sample-rate "$SAMPLE_RATE"

# Also copy to a stable path for convenience.
cp "$report" "$REPORTS_DIR/overhead-latest.md"
echo "Report: $report"
echo "Also: $REPORTS_DIR/overhead-latest.md"
cat "$report"
