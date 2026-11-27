#!/bin/bash
set -euo pipefail

root=$(cd -- "$(dirname -- "$0")" && pwd)
workspace=${ADAPTER_WORKSPACE:-/workspace}
rr_dir=${ADAPTER_RR_DIR:-/tmp/tracewick-rr}
rr_image=${ADAPTER_RR_IMAGE:-tracewick-cloud-php:8.5}
name=${ADAPTER_CONTAINER:-tracewick-psr15-overhead}
args=(
    --detach --shm-size=128m --name "$name" --network "${ADAPTER_NETWORK:-host}" --user "$(id -u):$(id -g)"
    --mount "type=bind,src=$root,dst=/probe/adapter-overhead,readonly"
    --mount "type=bind,src=$root/../runtime-preflight,dst=/probe/runtime-preflight,readonly"
    --mount "type=bind,src=$workspace/psr-15,dst=/workspace/psr-15,readonly"
    --env "TW_ENABLED=$2" --env "TRACEWICK_ENABLED=$2" --env "TW_OPERATIONS=$3"
)
rr_args=(
    --mount "type=bind,src=$rr_dir,dst=/rr,readonly"
    --mount "type=bind,src=$rr_dir/sockets.ini,dst=/usr/local/etc/php/conf.d/99-sockets.ini,readonly"
)

case "$1" in
    rr)
        docker run "${args[@]}" "${rr_args[@]}" "$rr_image" /rr/rr serve -c /probe/adapter-overhead/rr.yaml
        ;;
    swoole)
        docker run "${args[@]}" "${ADAPTER_SWOOLE_IMAGE:-tracewick-swoole-smoke:6.3.0}" php /probe/adapter-overhead/swoole.php
        ;;
    franken)
        docker run "${args[@]}" --env XDG_DATA_HOME=/tmp/caddy-data --env XDG_CONFIG_HOME=/tmp/caddy-config \
            "${ADAPTER_FRANKEN_IMAGE:-tracewick-frankenphp-smoke:1.14.0}" \
            frankenphp run --config /probe/adapter-overhead/Caddyfile --adapter caddyfile
        ;;
    laravel|symfony)
        laravel_enabled=false
        if [[ $2 == 1 ]]; then
            laravel_enabled=true
        fi
        docker run "${args[@]}" "${rr_args[@]}" \
            --mount "type=bind,src=${ADAPTER_FRAMEWORK_INPUTS:?Set ADAPTER_FRAMEWORK_INPUTS},dst=/framework-inputs,readonly" \
            --env "TW_FRAMEWORK=$1" --env "TRACEWICK_LARAVEL_ENABLED=$laravel_enabled" --env TRACEWICK_SPOOL_DIR=/dev/shm/spool \
            "$rr_image" /rr/rr serve -c /probe/adapter-overhead/framework.yaml
        ;;
    *)
        printf 'Unknown runtime %s\n' "$1" >&2
        exit 2
        ;;
esac
