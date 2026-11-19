<?php

declare(strict_types=1);

require __DIR__ . "/native.php";

$mode = $argv[1] ?? 'worker';
if ($mode === 'main') {
    echo json_encode(nativeWork(true)) . "\n";
} else {
    $runtimes = $futures = $rows = [];
    for ($i = 0; $i < (str_starts_with($mode, 'concurrent') ? 4 : 1); ++$i) {
        $runtimes[$i] = new parallel\Runtime(__DIR__ . "/native.php");
        $futures[$i] = $runtimes[$i]->run(static function (bool $profile, bool $trace): array {
            return nativeWork($profile, $trace);
        }, [$mode !== 'off', str_ends_with($mode, 'trace')]);
    }
    if (str_starts_with($mode, 'concurrent')) {
        $rows[] = nativeWork(true, str_ends_with($mode, 'trace'));
    }
    foreach ($futures as $f) {
        $rows[] = $f->value();
    }
    foreach ($runtimes as $r) {
        $r->close();
    }
    echo json_encode($rows) . "\n";
}
