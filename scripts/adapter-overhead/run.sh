#!/bin/bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
if (( $# < 4 )); then
    printf 'Usage: %s OUTPUT MEASUREMENT WARMUP RUNTIME:ENABLED:PAIR [...]\n' "$0" >&2
    exit 2
fi
name=${ADAPTER_CONTAINER:-tracewick-psr15-overhead}
if docker container inspect "$name" >/dev/null 2>&1; then
    exit 1
fi
mkdir -p "$1"
output=$(cd -- "$1" && pwd)
window=$2
warmup=$3
shift 3
ops=2600000
expected='2600000:1396360769'
rate=20

stop_stand() {
    docker stop --time 8 "$name" >/dev/null 2>&1 || true
    docker rm -f "$name" >/dev/null 2>&1 || true
}
cleanup() {
    local status=$?
    if (( status != 0 )) && [[ -n ${sample:-} ]]; then
        docker logs "$name" > "$sample/stand.log" 2>&1 || true
    fi
    stop_stand
}
trap cleanup EXIT

function request() {
    curl --fail --silent --show-error --max-time 2 "http://127.0.0.1:18150/$1"
}

function load() {
    docker run --rm --network host --user "$(id -u):$(id -g)" --mount "type=bind,src=$PWD,dst=/probe/adapter-overhead,readonly" --mount "type=bind,src=$sample,dst=/out" \
        --env "RATE=$rate" --env "DURATION=$1" --env "EXPECTED=$expected" --env "WORKER_PID=$pid" \
        "${ADAPTER_K6_IMAGE:-grafana/k6:1.8.2}" run --quiet --summary-export "/out/$2.json" /probe/adapter-overhead/overhead.js >"$sample/$2.txt" 2>&1
}

for arm in "$@"; do
    IFS=: read -r runtime enabled number <<< "$arm"
    if [[ ! $enabled =~ ^[01]$ || ! $number =~ ^[1-9][0-9]*$ ]]; then
        printf 'Invalid arm %s\n' "$arm" >&2
        exit 2
    fi
    sample="$output/$runtime-$enabled-$number"
    mkdir "$sample"
    printf '%s starting %s\n' "$(date -u +%T)" "$arm"
    ./start.sh "$runtime" "$enabled" "$ops" > "$sample/container-id"
    for i in {1..50}; do
        if request __ready >/dev/null 2>&1; then break; fi
        sleep 0.2
    done
    request __ready >/dev/null
    [[ "$(request work)" == "$expected" ]]
    request __worker > "$sample/worker-start.json"
    pid=$(python3 -c 'import sys,json; print(json.load(sys.stdin)["pid"])' < "$sample/worker-start.json")
    load "$warmup" warmup
    request __worker > "$sample/pre.json"
    start=$(date -u +%s.%N)
    load "$window" measurement
    end=$(date -u +%s.%N)
    request __worker > "$sample/post.json"
    printf '%s %s\n' "$start" "$end" > "$sample/timestamps"
    docker exec "$name" sh -c 'set -e; getconf CLK_TCK; if [ -d /dev/shm/spool ]; then find /dev/shm/spool -type f -name "*.spool" -printf "%P %s\n"; fi' > "$sample/spool.txt"
    profiles=$(tail -n +2 "$sample/spool.txt" | wc -l)
    if (( enabled == 1 && profiles == 0 || enabled == 0 && profiles > 0 )); then
        printf 'Unexpected spool count for %s: %s\n' "$arm" "$profiles" >&2
        exit 1
    fi
    docker logs "$name" > "$sample/stand.log" 2>&1
    printf '%s finished %s\n' "$(date -u +%T)" "$arm"
    stop_stand
done
