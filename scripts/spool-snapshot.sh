#!/usr/bin/env sh
# One-line spool snapshot: files,bytes,claimed (via app-fpm volume mount).
set -eu
compose=${COMPOSE:-docker compose}
$compose exec -T app-fpm php -r '
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
