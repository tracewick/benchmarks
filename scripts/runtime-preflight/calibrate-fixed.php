<?php

declare(strict_types=1);

require '/srv/app/fixed-work.php';

$iterations = 200000;
$initial = hrtime(true);
fixedStackWork(48, $iterations);
$elapsed = hrtime(true) - $initial;
$iterations = max(1000, min(10000000, (int) round($iterations * 25_000_000 / $elapsed)));
$durations = [];
for ($i = 0; $i < 7; ++$i) {
    $start = hrtime(true);
    $checksum = fixedStackWork(48, $iterations);
    $durations[] = (hrtime(true) - $start) / 1_000_000;
}
sort($durations);
echo json_encode([
    'iterations' => $iterations, 'checksum' => $checksum,
    'baseline_ms' => $durations, 'median_baseline_ms' => $durations[3],
    'note' => 'Calibrated once without profiling; operation count is fixed across all six arms.',
], JSON_THROW_ON_ERROR), "\n";
