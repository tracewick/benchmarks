#!/usr/bin/env bash
# Long soak: fixed RPS + docker stats for workload + reader → report.
# Designed to run under tmux/nohup so SSH logout does not stop the load.
# RUNTIME=fpm|rr|swoole  READER=drain|agent
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
RUNTIME=${RUNTIME:-fpm} # fpm | rr | swoole
STACK_DEPTH=${WORK_STACK_DEPTH:-0}
FPM_CHILDREN=${PHP_FPM_MAX_CHILDREN:-4}
RR_WORKERS=${RR_NUM_WORKERS:-4}
SWOOLE_WORKERS=${SWOOLE_WORKER_NUM:-4}

case "$RUNTIME" in
  fpm|rr|swoole) ;;
  *)
    echo "run-soak: RUNTIME must be fpm|rr|swoole (got: $RUNTIME)" >&2
    exit 2
    ;;
esac
case "$READER" in
  drain|agent) ;;
  *)
    echo "run-soak: READER must be drain|agent (got: $READER)" >&2
    exit 2
    ;;
esac

if [[ "$RUNTIME" == "rr" && "$BASE_URL" == "http://127.0.0.1:8080" ]]; then
  BASE_URL=http://127.0.0.1:8082
fi
if [[ "$RUNTIME" == "swoole" && "$BASE_URL" == "http://127.0.0.1:8080" ]]; then
  BASE_URL=http://127.0.0.1:8083
fi

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
echo "    RATE=$RATE DURATION=$DURATION SAMPLE_RATE=$SAMPLE_RATE STATS_INTERVAL=${STATS_INTERVAL}s"
echo "    RUNTIME=$RUNTIME READER=$READER WORK_STACK_DEPTH=$STACK_DEPTH"
echo "    run_dir=$run_dir"
echo "    tip: run inside tmux (tmux new -s soak) so logout does not kill k6"

{
  echo "started_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "RATE=$RATE"
  echo "DURATION=$DURATION"
  echo "TRACEWICK_SAMPLE_RATE=$SAMPLE_RATE"
  echo "STATS_INTERVAL=$STATS_INTERVAL"
  echo "READER=$READER"
  echo "RUNTIME=$RUNTIME"
  echo "WORK_STACK_DEPTH=$STACK_DEPTH"
  echo "PHP_FPM_MAX_CHILDREN=$FPM_CHILDREN"
  echo "RR_NUM_WORKERS=$RR_WORKERS"
  echo "SWOOLE_WORKER_NUM=$SWOOLE_WORKERS"
  echo "BASE_URL=$BASE_URL"
  echo "K6_IMAGE=$K6_IMAGE"
  echo "repo_sha=$(git rev-parse HEAD 2>/dev/null || echo unknown)"
  echo "host=$(uname -a)"
} > "$run_dir/meta.txt"

chmod +x "$ROOT/scripts/recreate-workload.sh" "$ROOT/scripts/ensure-reader.sh"
# Stop sibling runtimes so one VPS soak is not contended.
$COMPOSE stop app-fpm app-nginx app-rr app-swoole 2>/dev/null || true

TRACEWICK_ENABLED=1 \
TRACEWICK_SAMPLE_RATE="$SAMPLE_RATE" \
WORK_STACK_DEPTH="$STACK_DEPTH" \
PHP_FPM_MAX_CHILDREN="$FPM_CHILDREN" \
RR_NUM_WORKERS="$RR_WORKERS" \
SWOOLE_WORKER_NUM="$SWOOLE_WORKERS" \
RUNTIME="$RUNTIME" \
BASE_URL="$BASE_URL" \
  "$ROOT/scripts/recreate-workload.sh" | tee "$run_dir/health.json"

READER="$READER" "$ROOT/scripts/ensure-reader.sh"

case "$RUNTIME" in
  fpm) app_svc=app-fpm ;;
  rr) app_svc=app-rr ;;
  swoole) app_svc=app-swoole ;;
esac
if [[ "$READER" == "agent" ]]; then
  reader_svc=app-agent
else
  reader_svc=app-drain
fi

app_stats="$run_dir/${app_svc}-stats.csv"
reader_stats="$run_dir/${reader_svc}-stats.csv"
# Keep legacy filename for older summarize callers / muscle memory.
cp_link_fpm="$run_dir/app-fpm-stats.csv"

echo "==> Sampling docker stats every ${STATS_INTERVAL}s ($app_svc + $reader_svc)"
COMPOSE="$COMPOSE" "$ROOT/scripts/sample-container-stats.sh" "$app_svc" "$app_stats" "$STATS_INTERVAL" &
app_pid=$!
COMPOSE="$COMPOSE" "$ROOT/scripts/sample-container-stats.sh" "$reader_svc" "$reader_stats" "$STATS_INTERVAL" &
reader_pid=$!

cleanup() {
  kill "$app_pid" "$reader_pid" 2>/dev/null || true
  wait "$app_pid" 2>/dev/null || true
  wait "$reader_pid" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

sleep "$STATS_INTERVAL"

echo "==> k6 soak RATE=$RATE DURATION=$DURATION BASE_URL=$BASE_URL"
docker run --rm --network host \
  -v "$ROOT/generators/k6:/scripts:ro" \
  -v "$run_dir:/out" \
  -e BASE_URL="$BASE_URL" \
  -e RATE="$RATE" \
  -e DURATION="$DURATION" \
  "$K6_IMAGE" run /scripts/soak.js --summary-export=/out/k6.json

cleanup
trap - EXIT INT TERM

# Alias for summarize when runtime is fpm (historical path name).
if [[ "$app_svc" == "app-fpm" && ! -e "$cp_link_fpm" ]]; then
  ln -sf "$(basename "$app_stats")" "$cp_link_fpm" 2>/dev/null || cp "$app_stats" "$cp_link_fpm"
fi

host=$(uname -a)
sha=$(git rev-parse HEAD 2>/dev/null || echo unknown)
report="$run_dir/soak-report.md"

python3 "$ROOT/scripts/summarize-soak.py" \
  --k6 "$run_dir/k6.json" \
  --app-stats "$app_stats" \
  --reader-stats "$reader_stats" \
  --out "$report" \
  --repo-sha "$sha" \
  --host "$host" \
  --rate "$RATE" \
  --duration "$DURATION" \
  --sample-rate "$SAMPLE_RATE" \
  --runtime "$RUNTIME" \
  --reader "$READER" \
  --stack-depth "$STACK_DEPTH" \
  --app-service "$app_svc" \
  --reader-service "$reader_svc"

cp "$report" "$REPORTS_DIR/soak-latest.md"
echo "finished_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$run_dir/meta.txt"
echo "Report: $report"
echo "Also: $REPORTS_DIR/soak-latest.md"
