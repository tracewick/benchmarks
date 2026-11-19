#!/bin/sh
# Read only this container's process namespace. The probe itself is excluded.
set -eu
self=$$
read_failed() {
    # A healthcheck can exit between any two /proc reads. A missing service
    # process is still rejected by the process identity continuity validator.
    [ ! -e "$path" ] && return
    printf 'Cannot read %s for PID %s (%s)\n' "$1" "$pid" "${name:-unknown}" >&2
    exit 1
}
for path in /proc/[0-9]*; do
    pid=${path##*/}
    [ "$pid" = "$self" ] && continue
    [ -r "$path/stat" ] && [ -r "$path/status" ] || continue
    name=$(cat "$path/comm" 2>/dev/null) || { read_failed comm; continue; }
    case "$name" in rr|php|php-fpm*|tracewick-agent) ;; *) continue ;; esac
    args=$(tr '\000' ' ' < "$path/cmdline" 2>/dev/null) || { read_failed cmdline; continue; }
    # An exiting process may already have an empty cmdline. Healthchecks are
    # transient diagnostics, including when caught during process teardown.
    case "$args" in ''|*'exit(extension_loaded'*) continue ;; esac
    stat=$(cat "$path/stat" 2>/dev/null) || { read_failed stat; continue; }
    status=$(cat "$path/status" 2>/dev/null) || { read_failed status; continue; }
    fds=$(find "$path/fd" -mindepth 1 -maxdepth 1 2>/dev/null) || { read_failed fd; continue; }
    # Publish complete records only. A disappearing process cannot leave a
    # partial record that gets mistaken for a malformed worker observation.
    printf '@ %s\n%s\n%s\nFDs:\t' "$pid" "$stat" "$status"
    if [ -n "$fds" ]; then printf '%s\n' "$fds" | wc -l; else printf '0\n'; fi
    printf '@end\n'
done
