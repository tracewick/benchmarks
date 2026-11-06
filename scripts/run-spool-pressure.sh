#!/usr/bin/env bash
# M3: stop drain, fill spool toward max_files, prove HTTP stays green, then drain catch-up.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

COMPOSE=${COMPOSE:-docker compose}
K6_IMAGE=${K6_IMAGE:-grafana/k6:1.8.2}
REPORTS_DIR=${REPORTS_DIR:-reports/_local}
BASE_URL=${BASE_URL:-http://127.0.0.1:8080}
RATE=${RATE:-20}
DURATION=${DURATION:-90s}
MAX_FILES=${TRACEWICK_SPOOL_MAX_FILES:-80}
SAMPLE_RATE=${TRACEWICK_SAMPLE_RATE:-1.0}
STATS_INTERVAL=${STATS_INTERVAL:-2}
STACK_DEPTH=${WORK_STACK_DEPTH:-0}
READER=${READER:-drain} # drain | agent | off (off = stop reader during fill; restart for catch-up)

if [[ "$REPORTS_DIR" != /* ]]; then
  REPORTS_DIR="$ROOT/$REPORTS_DIR"
fi

mkdir -p "$REPORTS_DIR"
chmod a+rwx "$REPORTS_DIR" || true
stamp=$(date -u +%Y%m%dT%H%M%SZ)
run_dir="$REPORTS_DIR/spool-pressure-$stamp"
mkdir -p "$run_dir"
chmod a+rwx "$run_dir" || true

echo "ts_unix,files,bytes,claimed_or_tmp" > "$run_dir/spool-timeseries.csv"

record_spool() {
  local label=$1
  local line ts
  ts=$(date +%s)
  line=$("$ROOT/scripts/spool-snapshot.sh")
  echo "$ts,$line" >> "$run_dir/spool-timeseries.csv"
  echo "$line" | tee "$run_dir/$label.txt"
}

echo "==> Recreate app-fpm (enabled, sampleRate=$SAMPLE_RATE, maxFiles=$MAX_FILES, WORK_STACK_DEPTH=$STACK_DEPTH)"
TRACEWICK_ENABLED=1 TRACEWICK_SAMPLE_RATE="$SAMPLE_RATE" TRACEWICK_SPOOL_MAX_FILES="$MAX_FILES" \
  WORK_STACK_DEPTH="$STACK_DEPTH" \
  $COMPOSE up -d --force-recreate --no-deps app-fpm
$COMPOSE up -d --no-deps --force-recreate app-nginx
for i in $(seq 1 60); do curl -sf "$BASE_URL/health" >/dev/null && break; sleep 1; done
curl -sf "$BASE_URL/health" | tee "$run_dir/health.json"; echo

echo "==> Stop readers (build queue); catch-up reader=$READER"
chmod +x "$ROOT/scripts/ensure-reader.sh"
READER=off "$ROOT/scripts/ensure-reader.sh"
# Catch-up always uses a real reader (default drain); "off" here means drain for restore.
CATCHUP_READER=$READER
if [[ "$CATCHUP_READER" == "off" ]]; then
  CATCHUP_READER=drain
fi

# Clear leftover spool so the ceiling is measurable.
$COMPOSE exec -T app-fpm php -r '
$dir="/var/spool/tracewick";
$it=new RecursiveIteratorIterator(new RecursiveDirectoryIterator($dir, FilesystemIterator::SKIP_DOTS), RecursiveIteratorIterator::CHILD_FIRST);
foreach ($it as $f) {
  if ($f->isFile()) @unlink($f->getPathname());
}
'
echo "spool cleared"
record_spool spool-before

echo "==> Sample spool while k6 runs"
(
  while :; do
    ts=$(date +%s)
    line=$("$ROOT/scripts/spool-snapshot.sh" || echo "0,0,0")
    echo "$ts,$line" >> "$run_dir/spool-timeseries.csv"
    sleep "$STATS_INTERVAL"
  done
) &
sampler=$!

docker run --rm --network host \
  -v "$ROOT/generators/k6:/scripts:ro" \
  -v "$run_dir:/out" \
  -e BASE_URL="$BASE_URL" \
  -e RATE="$RATE" \
  -e DURATION="$DURATION" \
  -e EXPECT_PROFILING=1 \
  "$K6_IMAGE" run /scripts/overhead.js --summary-export=/out/k6.json

kill "$sampler" 2>/dev/null || true
wait "$sampler" 2>/dev/null || true

record_spool spool-after-load
peak_files=$(awk -F, 'NR>1 {if($2>m)m=$2} END{print m+0}' "$run_dir/spool-timeseries.csv")
peak_bytes=$(awk -F, 'NR>1 {if($3>m)m=$3} END{print m+0}' "$run_dir/spool-timeseries.csv")
echo "peak_files=$peak_files max_files=$MAX_FILES peak_bytes=$peak_bytes" | tee "$run_dir/peak.txt"

echo "==> Start reader=$CATCHUP_READER; measure catch-up"
start=$(date +%s)
READER="$CATCHUP_READER" "$ROOT/scripts/ensure-reader.sh"
# wait until regular spool files ~0 (allow brief claim churn)
deadline=$((start + 180))
while :; do
  line=$("$ROOT/scripts/spool-snapshot.sh")
  files=$(printf '%s' "$line" | cut -d, -f1)
  echo "$(date +%s),$line" >> "$run_dir/spool-timeseries.csv"
  if [ "${files:-0}" -le 2 ]; then
    break
  fi
  if [ "$(date +%s)" -ge "$deadline" ]; then
    echo "WARN: spool not drained within 180s (files=$files)" | tee "$run_dir/drain-timeout.txt"
    break
  fi
  sleep 2
done
end=$(date +%s)
echo "drain_catchup_sec=$((end - start))" | tee "$run_dir/drain-catchup.txt"
echo "reader=$CATCHUP_READER" | tee -a "$run_dir/drain-catchup.txt"
record_spool spool-after-drain

fail=$(python3 - <<PY
import json
d=json.load(open("$run_dir/k6.json"))
v=d.get("metrics",{}).get("http_req_failed",{}).get("value")
print(0 if v is None else v)
PY
)
rps=$(python3 - <<PY
import json
d=json.load(open("$run_dir/k6.json"))
print(d.get("metrics",{}).get("http_reqs",{}).get("rate",""))
PY
)

sha=$(git rev-parse HEAD 2>/dev/null || echo unknown)
host=$(uname -a)
{
  echo "started_at_utc=$stamp"
  echo "RATE=$RATE"
  echo "DURATION=$DURATION"
  echo "TRACEWICK_SAMPLE_RATE=$SAMPLE_RATE"
  echo "TRACEWICK_SPOOL_MAX_FILES=$MAX_FILES"
  echo "WORK_STACK_DEPTH=$STACK_DEPTH"
  echo "READER=$CATCHUP_READER"
  echo "repo_sha=$sha"
  echo "host=$host"
} > "$run_dir/meta.txt"

peak_mib=$(python3 -c "print(f'{$peak_bytes/1024/1024:.2f}')")
catchup=$(cat "$run_dir/drain-catchup.txt" 2>/dev/null || true)

report="$run_dir/spool-pressure-report.md"
cat > "$report" <<EOF
# Report: spool pressure — $(date -u +%Y-%m-%d)

Methodology: [METHOD.md](../../METHOD.md) layer B.

## Setup

| Field | Value |
| --- | --- |
| Host run dir | \`$run_dir\` |
| Host | $host |
| repo SHA | \`$sha\` |
| sampleRate | \`$SAMPLE_RATE\` |
| TRACEWICK_SPOOL_MAX_FILES | \`$MAX_FILES\` |
| WORK_STACK_DEPTH | $STACK_DEPTH |
| Catch-up reader | \`$CATCHUP_READER\` |
| RATE / duration | $RATE / $DURATION |
| Reader during load | **stopped** |

## Results

| Metric | Value |
| --- | --- |
| Peak spool files | $peak_files (cap $MAX_FILES) |
| Peak spool bytes | $peak_bytes ($peak_mib MiB) |
| HTTP fail rate during fill | $fail |
| Achieved RPS | $rps |
| Drain catch-up | $catchup |

## Interpretation

- Spool grew while drain was down; HTTP should stay green (fail-open / soft admission).
- Peak near \`max_files\` implies further profiles were dropped at admission (soft).
- After drain restart, queue should shrink (catch-up lag).
- Depth > 0 increases bytes per file vs shallow \`busyWork\` (same wall budget).

## Artifacts

- \`k6.json\`, \`spool-timeseries.csv\`, health + spool snapshots in this directory.
EOF

cp "$report" "$REPORTS_DIR/spool-pressure-latest.md"
echo "Report: $report"
cat "$report"
