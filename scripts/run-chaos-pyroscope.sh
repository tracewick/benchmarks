#!/usr/bin/env bash
# M3 optional: Toxiproxy latency to Pyroscope → spool backs up while app stays green.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

COMPOSE=${COMPOSE:-docker compose}
K6_IMAGE=${K6_IMAGE:-grafana/k6:1.8.2}
REPORTS_DIR=${REPORTS_DIR:-reports/_local}
BASE_URL=${BASE_URL:-http://127.0.0.1:8080}
TOXIPROXY_URL=${TOXIPROXY_URL:-http://127.0.0.1:8474}
RATE=${RATE:-20}
DURATION=${DURATION:-60s}
LATENCY_MS=${LATENCY_MS:-3000}
SAMPLE_RATE=${TRACEWICK_SAMPLE_RATE:-1.0}

if [[ "$REPORTS_DIR" != /* ]]; then
  REPORTS_DIR="$ROOT/$REPORTS_DIR"
fi
mkdir -p "$REPORTS_DIR"
chmod a+rwx "$REPORTS_DIR" || true
stamp=$(date -u +%Y%m%dT%H%M%SZ)
run_dir="$REPORTS_DIR/chaos-pyroscope-$stamp"
mkdir -p "$run_dir"
chmod a+rwx "$run_dir" || true

echo "ts_unix,files,bytes,claimed_or_tmp" > "$run_dir/spool-timeseries.csv"

echo "==> Ensure toxiproxy + stack"
$COMPOSE --profile chaos up -d --wait pyroscope grafana toxiproxy app-fpm app-nginx
# wait pyroscope/app
for i in $(seq 1 90); do curl -sf http://127.0.0.1:4040/ready >/dev/null && break; sleep 1; done
for i in $(seq 1 60); do curl -sf "$BASE_URL/health" >/dev/null && break; sleep 1; done

echo "==> Drain via toxiproxy:14040"
TRACEWICK_PYROSCOPE_URL=http://toxiproxy:14040 \
  $COMPOSE up -d --force-recreate --no-deps app-drain

# Clear toxics, then add latency
curl -sf -X POST "$TOXIPROXY_URL/reset" >/dev/null || true
curl -sf -X POST "$TOXIPROXY_URL/proxies/pyroscope/toxics" \
  -H 'Content-Type: application/json' \
  -d "{\"name\":\"pyroscope_latency\",\"type\":\"latency\",\"attributes\":{\"latency\":$LATENCY_MS,\"jitter\":0}}" \
  | tee "$run_dir/toxic.json"
echo

TRACEWICK_ENABLED=1 TRACEWICK_SAMPLE_RATE="$SAMPLE_RATE" \
  $COMPOSE up -d --force-recreate --no-deps app-fpm
# nginx resolves app-fpm at start; recreate changes the container IP.
$COMPOSE up -d --no-deps --force-recreate app-nginx
for i in $(seq 1 60); do curl -sf "$BASE_URL/health" >/dev/null && break; sleep 1; done
curl -sf "$BASE_URL/health" | tee "$run_dir/health.json"; echo

# Clear spool
$COMPOSE exec -T app-fpm php -r '
$dir="/var/spool/tracewick";
$it=new RecursiveIteratorIterator(new RecursiveDirectoryIterator($dir, FilesystemIterator::SKIP_DOTS), RecursiveIteratorIterator::CHILD_FIRST);
foreach ($it as $f) { if ($f->isFile()) @unlink($f->getPathname()); }
'

(
  while :; do
    ts=$(date +%s)
    line=$("$ROOT/scripts/spool-snapshot.sh" || echo "0,0,0")
    echo "$ts,$line" >> "$run_dir/spool-timeseries.csv"
    sleep 2
  done
) &
sampler=$!

# Collect summary even if thresholds fail (we still want the chaos report).
set +e
docker run --rm --network host \
  -v "$ROOT/generators/k6:/scripts:ro" \
  -v "$run_dir:/out" \
  -e BASE_URL="$BASE_URL" \
  -e RATE="$RATE" \
  -e DURATION="$DURATION" \
  -e EXPECT_PROFILING=1 \
  "$K6_IMAGE" run /scripts/overhead.js --summary-export=/out/k6.json
k6_rc=$?
set -e

kill "$sampler" 2>/dev/null || true
wait "$sampler" 2>/dev/null || true

peak=$(awk -F, 'NR>1 {if($2>m)m=$2} END{print m+0}' "$run_dir/spool-timeseries.csv")
echo "peak_files=$peak k6_rc=$k6_rc" | tee "$run_dir/peak.txt"

echo "==> Remove toxic; restore direct Pyroscope URL"
curl -sf -X DELETE "$TOXIPROXY_URL/proxies/pyroscope/toxics/pyroscope_latency" >/dev/null || true
TRACEWICK_PYROSCOPE_URL=http://pyroscope:4040 \
  $COMPOSE up -d --force-recreate --no-deps app-drain

fail=$(python3 - <<PY
import json
from pathlib import Path
p=Path("$run_dir/k6.json")
if not p.is_file():
    print("missing")
else:
    d=json.load(p.open())
    print(d.get("metrics",{}).get("http_req_failed",{}).get("value",0))
PY
)

cat > "$run_dir/chaos-report.md" <<EOF
# Report: chaos Pyroscope latency — $(date -u +%Y-%m-%d)

| Field | Value |
| --- | --- |
| Toxic | latency ${LATENCY_MS}ms on toxiproxy→pyroscope |
| RATE / duration | $RATE / $DURATION |
| sampleRate | $SAMPLE_RATE |
| Peak spool files during toxic | $peak |
| HTTP fail rate | $fail |

App requests should remain healthy while delivery slows and spool grows.
EOF
cp "$run_dir/chaos-report.md" "$REPORTS_DIR/chaos-pyroscope-latest.md"
cat "$run_dir/chaos-report.md"
