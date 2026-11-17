<?php

declare(strict_types=1);

$directory = getenv('TRACEWICK_SPOOL_DIR') ?: '/var/spool/tracewick';
$pending = 0;
$rejected = 0;
$bytes = 0;
$seen = 0;
$oldest = time();
foreach (new RecursiveIteratorIterator(new RecursiveDirectoryIterator($directory, FilesystemIterator::SKIP_DOTS)) as $file) {
    if (++$seen > 100000) {
        throw new RuntimeException('Spool probe scan budget exceeded');
    }
    if (!$file->isFile()) {
        continue;
    }
    try {
        $size = $file->getSize();
        $modified = $file->getMTime();
    } catch (RuntimeException $error) {
        // A concurrent ack/rename is normal; other filesystem failures are not zero backlog.
        if (!file_exists($file->getPathname())) {
            continue;
        }
        throw $error;
    }
    if (str_contains($file->getPathname(), '/rejected/')) {
        ++$rejected;
    } else {
        // Include claims and in-progress temporary files: neither means an empty spool.
        ++$pending;
        $bytes += $size;
        $oldest = min($oldest, $modified);
    }
}
echo json_encode(['pending_files' => $pending, 'pending_bytes' => $bytes,
    'oldest_age_seconds' => $pending ? max(0, time() - $oldest) : 0,
    'rejected_files' => $rejected], JSON_THROW_ON_ERROR);
