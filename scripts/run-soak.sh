#!/usr/bin/env bash
# Long soak: fixed RPS + docker stats for app-fpm and app-drain → report.
# Designed to run under tmux/nohup so SSH logout does not stop the load.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

COMPOSE=${COMPOSE:-docker compose}
K6_IMAGE=${K6_IMAGE:-grafana/k6:1.8.2}
REPORTS_DIR=${REPORTS_DIR:-reports/_local}
BASE_URL=${BASE_URL:-http://127.0.0.1:8080}
RATE=${RATE:-10}
DURATION=${DURATION:-72h}
SAMPLE_RATE=${TRACEWICK_SAMPLE_RATE:-0.1}
STATS_INTERVAL=${STATS_INTERVAL:-60}
READER=${READER:-drain} # drain | agent

if [[ "$REPORTS_DIR" != /* ]]; then
  REPORTS_DIR="$ROOT/$REPORTS_DIR"
fi

mkdir -p "$REPORTS_DIR"
chmod a+rwx "$REPORTS_DIR" || true

stamp=$(date -u +%Y%m%dT%H%M%SZ)
run_dir="$REPORTS_DIR/soak-$stamp"
mkdir -p "$run_dir"
chmod a+rwx "$run_dir" || true

log="$run_dir/soak.log"
exec > >(tee -a "$log") 2>&1

echo "==> Soak start $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "    RATE=$RATE DURATION=$DURATION SAMPLE_RATE=$SAMPLE_RATE STATS_INTERVAL=${STATS_INTERVAL}s READER=$READER"
echo "    run_dir=$run_dir"
echo "    tip: run inside tmux (tmux new -s soak) so logout does not kill k6"

{
  echo "started_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "RATE=$RATE"
  echo "DURATION=$DURATION"
  echo "TRACEWICK_SAMPLE_RATE=$SAMPLE_RATE"
  echo "STATS_INTERVAL=$STATS_INTERVAL"
  echo "READER=$READER"
  echo "BASE_URL=$BASE_URL"
  echo "K6_IMAGE=$K6_IMAGE"
  echo "repo_sha=$(git rev-parse HEAD 2>/dev/null || echo unknown)"
  echo "host=$(uname -a)"
} > "$run_dir/meta.txt"

echo "==> Recreating app-fpm (profiling on)"
TRACEWICK_ENABLED=1 TRACEWICK_SAMPLE_RATE="$SAMPLE_RATE" \
  $COMPOSE up -d --force-recreate --no-deps app-fpm
$COMPOSE up -d --no-deps --force-recreate app-nginx
chmod +x "$ROOT/scripts/ensure-reader.sh"
READER="$READER" "$ROOT/scripts/ensure-reader.sh"

for i in $(seq 1 60); do
  if curl -sf "$BASE_URL/health" >/dev/null; then
    break
  fi
  sleep 1
done
curl -sf "$BASE_URL/health" | tee "$run_dir/health.json"
echo

fpm_stats="$run_dir/app-fpm-stats.csv"
if [[ "$READER" == "agent" ]]; then
  reader_svc=app-agent
else
  reader_svc=app-drain
fi
reader_stats="$run_dir/${reader_svc}-stats.csv"

echo "==> Sampling docker stats every ${STATS_INTERVAL}s ($reader_svc)"
COMPOSE="$COMPOSE" "$ROOT/scripts/sample-container-stats.sh" app-fpm "$fpm_stats" "$STATS_INTERVAL" &
fpm_pid=$!
COMPOSE="$COMPOSE" "$ROOT/scripts/sample-container-stats.sh" "$reader_svc" "$reader_stats" "$STATS_INTERVAL" &
drain_pid=$!

cleanup() {
  kill "$fpm_pid" "$drain_pid" 2>/dev/null || true
  wait "$fpm_pid" 2>/dev/null || true
  wait "$drain_pid" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

sleep "$STATS_INTERVAL"

echo "==> k6 soak RATE=$RATE DURATION=$DURATION"
# --rm so the container does not linger; network host for BASE_URL on the VM.
docker run --rm --network host \
  -v "$ROOT/generators/k6:/scripts:ro" \
  -v "$run_dir:/out" \
  -e BASE_URL="$BASE_URL" \
  -e RATE="$RATE" \
  -e DURATION="$DURATION" \
  "$K6_IMAGE" run /scripts/soak.js --summary-export=/out/k6.json

cleanup
trap - EXIT INT TERM

host=$(uname -a)
sha=$(git rev-parse HEAD 2>/dev/null || echo unknown)
report="$run_dir/soak-report.md"

python3 "$ROOT/scripts/summarize-soak.py" \
  --k6 "$run_dir/k6.json" \
  --fpm-stats "$fpm_stats" \
  --drain-stats "$reader_stats" \
  --out "$report" \
  --repo-sha "$sha" \
  --host "$host" \
  --rate "$RATE" \
  --duration "$DURATION" \
  --sample-rate "$SAMPLE_RATE"

cp "$report" "$REPORTS_DIR/soak-latest.md"
echo "finished_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$run_dir/meta.txt"
echo "Report: $report"
echo "Also: $REPORTS_DIR/soak-latest.md"
