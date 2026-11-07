#!/usr/bin/env sh
# One-line spool snapshot: files,bytes,claimed (via workload volume mount).
# Prefer RUNTIME=fpm|rr|swoole → app-*; else SPOOL_SVC; else first running among them.
set -eu
compose=${COMPOSE:-docker compose}
runtime=${RUNTIME:-}
svc=${SPOOL_SVC:-}

case "$runtime" in
  fpm) svc=app-fpm ;;
  rr) svc=app-rr ;;
  swoole) svc=app-swoole ;;
esac

if [ -z "$svc" ]; then
  for cand in app-fpm app-rr app-swoole; do
    if $compose ps --status running -q "$cand" >/dev/null 2>&1 \
      && [ -n "$($compose ps --status running -q "$cand" 2>/dev/null || true)" ]; then
      svc=$cand
      break
    fi
  done
fi

if [ -z "$svc" ]; then
  echo "spool-snapshot: no running workload (set RUNTIME or SPOOL_SVC)" >&2
  echo "0,0,0"
  exit 0
fi

$compose exec -T "$svc" php -r '
$dir = getenv("TRACEWICK_SPOOL_DIR") ?: "/var/spool/tracewick";
$files = 0; $bytes = 0; $claimed = 0;
$it = new RecursiveIteratorIterator(new RecursiveDirectoryIterator($dir, FilesystemIterator::SKIP_DOTS));
foreach ($it as $f) {
    if (!$f->isFile()) { continue; }
    $name = $f->getFilename();
    if (str_ends_with($name, ".spool") && !str_starts_with($name, ".")) {
        $files++;
        $bytes += $f->getSize();
    } elseif (str_contains($name, ".claimed") || str_starts_with($name, ".")) {
        $claimed++;
        $bytes += $f->getSize();
    }
}
echo $files, ",", $bytes, ",", $claimed, "\n";
'
