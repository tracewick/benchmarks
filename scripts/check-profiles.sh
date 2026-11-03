#!/usr/bin/env sh
# Confirm smoke profiles reached Pyroscope (service_name=benchmarks-workload, route=work).
# Usage: PYROSCOPE_URL=http://127.0.0.1:4040 ./scripts/check-profiles.sh
set -eu

pyroscope=${PYROSCOPE_URL:-http://127.0.0.1:4040}
timeout=${TIMEOUT:-60}
out=${OUT:-}

query() {
    curl -fsS -H 'Content-Type: application/json' -d "$2" "$pyroscope/querier.v1.QuerierService/$1"
}

start_ms=$(( $(date +%s) * 1000 - 600000 ))
deadline=$(( $(date +%s) + timeout ))
selector='{service_name=\"benchmarks-workload\"}'

echo "Waiting for Pyroscope service_name=benchmarks-workload (route=work)…"
while :; do
    end_ms=$(( $(date +%s) * 1000 + 60000 ))
    routes=$(query LabelValues "{\"name\":\"route\",\"matchers\":[\"$selector\"],\"start\":$start_ms,\"end\":$end_ms}" || echo '{}')
    if echo "$routes" | grep -q '"work"'; then
        echo "OK: $routes"
        if [ -n "$out" ]; then
            echo "$routes" > "$out"
        fi
        exit 0
    fi
    if [ "$(date +%s)" -ge "$deadline" ]; then
        echo "Pyroscope did not show route=work for benchmarks-workload within ${timeout}s: $routes" >&2
        exit 1
    fi
    sleep 2
done
