<?php

declare(strict_types=1);
require __DIR__ . '/Probe.php';

use Tracewick\Sampler\ExcimerSampler;
use Tracewick\Sampler\SamplerConfig;

function compute(int $depth, int $iterations, int $value): int {
    if ($depth > 0) { return compute($depth - 1, $iterations, $value); }
    for ($i = 0; $i < $iterations; ++$i) {
        $value = ($value * 1664525 + 1013904223) & 0x7fffffff;
    }
    return $value;
}
function cpuNs(): int {
    $u = getrusage();
    return ($u['ru_utime.tv_sec'] + $u['ru_stime.tv_sec']) * 1_000_000_000
        + ($u['ru_utime.tv_usec'] + $u['ru_stime.tv_usec']) * 1000;
}
[, $mode, $hz, $depth, $cycles] = $argv;
[$hz, $depth, $cycles] = array_map('intval', [$hz, $depth, $cycles]);
$iterations = 33554432;
$provider = experimentProvider();
$t = $provider->getTracer('window');
$parent = $t->spanBuilder('parent')->startSpan();
$scope = $parent->activate();
$child = $t->spanBuilder('child')->startSpan();
experimentContext();
$p = $sampler = null;
$callbacks = 0;
if (in_array($mode, ['history','deferred'], true)) {
    $p = new Probe($mode, $hz, $depth);
} elseif ($mode !== 'off') {
    $size = $mode === 'batched' ? 10000 : 1;
    $sampler = new ExcimerSampler(new SamplerConfig(periodNs: intdiv(1000000000, $hz), maxDepth: $depth, maxSamples: $size));
    $native = (new ReflectionProperty($sampler, 'profiler'))->getValue($sampler);
    $original = (new ReflectionMethod($sampler, 'onNativeFlush'))->getClosure($sampler);
    $native->setFlushCallback(static function (ExcimerLog $log) use ($original, &$callbacks, $mode) {
        ++$callbacks;
        if ($mode === 'otel' && count($log) === 1) { experimentContext(); }
        $original($log);
    }, $size);
}

compute($depth, 100000, 1);
$checksum = 12345;
$block = intdiv($iterations, 2 * $cycles);
memory_reset_peak_usage();
$cpu = cpuNs();
$start = hrtime(true);
$sampler?->start();
$p?->native->start();
$work = hrtime(true);
for ($i = 0; $i < $cycles; ++$i) {
    $checksum = compute($depth, $block, $checksum);
    $p?->beforeChange(); $active = $child->activate(); $p?->afterChange();
    $checksum = compute($depth, $block, $checksum);
    $p?->beforeChange(); $active->detach(); $p?->afterChange();
}
$workEnd = hrtime(true);
$sampler?->stop();
$p?->native->stop();
$flushStart = hrtime(true);
$weights = $p?->drain() ?? [];
$batch = $sampler?->flush();
$end = hrtime(true);
$totalCpu = cpuNs() - $cpu;
$result = compact('mode','hz','depth','cycles','checksum','iterations') + [
    'total_cpu_ns' => $totalCpu, 'work_wall_ns' => $workEnd - $work,
    'total_wall_ns' => $end - $start, 'final_flush_ns' => $end - $flushStart,
    'peak_php_bytes' => memory_get_peak_usage(), 'max_rss_kib' => getrusage()['ru_maxrss'],
    'callbacks' => $p?->callbacks ?? $callbacks, 'changes' => 2 * $cycles,
    'queue_peak' => $p?->queuePeak, 'overflow' => $p?->overflow,
    'weight' => $batch?->eventCount() ?? array_sum($weights), 'unknown_weight' => $weights[''] ?? 0,
];
if (($sampler?->failureCount() ?? 0) || ($mode !== 'off' && !$result['weight'])) {
    throw new RuntimeException('Invalid timing row');
}
echo json_encode($result, JSON_THROW_ON_ERROR), "\n";
$scope->detach(); $child->end(); $parent->end(); $provider->shutdown();
