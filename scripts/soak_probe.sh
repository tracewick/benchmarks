#!/bin/sh
# Read only this container's process namespace. The probe itself is excluded.
set -eu
self=$$
for path in /proc/[0-9]*; do
    pid=${path##*/}
    [ "$pid" = "$self" ] && continue
    [ -r "$path/stat" ] && [ -r "$path/status" ] || continue
    # Observe service/worker processes, not transient runc/exec/healthcheck helpers.
    name=$(cat "$path/comm" 2>/dev/null) || {
        [ ! -e "$path" ] && continue
        exit 1
    }
    case "$name" in rr|php|php-fpm*|tracewick-agent) ;; *) continue ;; esac
    # Compose's extension healthcheck is a transient diagnostic, not a worker.
    args=$(tr '\000' ' ' < "$path/cmdline" 2>/dev/null) || {
        [ ! -e "$path" ] && continue
        exit 1
    }
    case "$args" in *'exit(extension_loaded'*) continue ;; esac
    printf '@ %s\n' "$pid"
    cat "$path/stat" 2>/dev/null || exit 1
    cat "$path/status" 2>/dev/null || exit 1
    printf 'FDs:\t'
    # Failure must not become a convincing zero descriptor count.
    fds=$(find "$path/fd" -mindepth 1 -maxdepth 1 2>/dev/null) || exit 1
    if [ -n "$fds" ]; then printf '%s\n' "$fds" | wc -l; else printf '0\n'; fi
    printf '@end\n'
done
