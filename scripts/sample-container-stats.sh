#!/usr/bin/env sh
# Sample docker stats for one compose service until SIGINT/SIGTERM.
# Usage: sample-container-stats.sh <compose-service> <output.csv> [interval_sec]
set -eu

service=${1:?service name required}
out=${2:?output csv path required}
interval=${3:-2}
compose=${COMPOSE:-docker compose}

cid=$($compose ps -q "$service")
if [ -z "$cid" ]; then
    echo "container for service $service not found" >&2
    exit 1
fi

echo "ts_unix,cpu_percent,mem_usage_bytes,mem_limit_bytes,mem_percent" > "$out"

cleanup() { exit 0; }
trap cleanup INT TERM

to_bytes() {
    python3 -c '
import sys
s=sys.argv[1].strip().replace(",","")
units={"B":1,"KiB":1024,"MiB":1024**2,"GiB":1024**3,"TiB":1024**4,"kB":1000,"MB":1000**2,"GB":1000**3}
for u in sorted(units, key=len, reverse=True):
    if s.endswith(u):
        print(int(float(s[: -len(u)]) * units[u]))
        break
else:
    print(0)
' "$1"
}

while :; do
    line=$(docker stats --no-stream --format '{{.CPUPerc}}|{{.MemUsage}}' "$cid" 2>/dev/null || true)
    if [ -n "$line" ]; then
        cpu=$(printf '%s' "$line" | cut -d'|' -f1 | tr -d ' %')
        memraw=$(printf '%s' "$line" | cut -d'|' -f2-)
        used=$(printf '%s' "$memraw" | awk -F'/' '{gsub(/^ +| +$/, "", $1); print $1}')
        lim=$(printf '%s' "$memraw" | awk -F'/' '{gsub(/^ +| +$/, "", $2); print $2}')
        used_b=$(to_bytes "$used")
        lim_b=$(to_bytes "$lim")
        if [ "$lim_b" -gt 0 ]; then
            pct=$(python3 -c "print(round($used_b * 100.0 / $lim_b, 3))")
        else
            pct=0
        fi
        echo "$(date +%s),${cpu},${used_b},${lim_b},${pct}" >> "$out"
    fi
    sleep "$interval"
done
