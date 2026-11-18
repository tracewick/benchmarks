<?php

declare(strict_types=1);

require __DIR__ . '/bootstrap.php';

use Tracewick\Sampler\ExcimerSampler;
use Tracewick\Sampler\SamplerConfig;

function fixedWork(int $iterations): int
{
    $value = 12345;
    for ($i = 0; $i < $iterations; ++$i) {
        $value = ($value * 1664525 + 1013904223) & 0x7fffffff;
    }
    return $value;
}
function atDepth(int $depth, int $iterations): int
{
    return $depth > 0 ? atDepth($depth - 1, $iterations) : fixedWork($iterations);
}
function cpuNs(array $usage): int
{
    return (int) (($usage['ru_utime.tv_sec'] + $usage['ru_stime.tv_sec']) * 1_000_000_000
        + ($usage['ru_utime.tv_usec'] + $usage['ru_stime.tv_usec']) * 1000);
}

[$script, $mode, $hz, $depth, $iterations] = $argv;
$hz = (int) $hz; $depth = (int) $depth; $iterations = (int) $iterations;
if (!in_array($mode, ['off', 'batched', 'immediate', 'otel'], true) || $hz < 1 || $depth < 1 || $iterations < 1) {
    throw new InvalidArgumentException('Invalid measurement parameters.');
}
if (ini_get('pcov.enabled') === '1' || ini_get('opcache.enable_cli') === '1') {
    throw new RuntimeException('Run with PCOV and CLI opcache disabled.');
}
$provider = experimentProvider();
$span = $provider->getTracer('callback-overhead')->spanBuilder('measured-work')->startSpan();
$scope = $span->activate();
if (!$span->isRecording()) { throw new RuntimeException('Expected a real recording SDK span.'); }
experimentContext();
$sampler = $mode === 'off' ? null : new ExcimerSampler(new SamplerConfig(
    periodNs: intdiv(1_000_000_000, $hz), maxDepth: $depth,
    maxSamples: $mode === 'batched' ? 10_000 : 1,
));
$callbacks = 0; $reads = 0;
if ($sampler !== null && in_array($mode, ['immediate', 'otel'], true)) {
    $native = (new ReflectionProperty($sampler, 'profiler'))->getValue($sampler);
    $original = (new ReflectionMethod($sampler, 'onNativeFlush'))->getClosure($sampler);
    $native->setFlushCallback(static function (ExcimerLog $log) use ($original, $mode, &$callbacks, &$reads): void {
        ++$callbacks;
        if ($mode === 'otel' && count($log) === 1) { experimentContext(); ++$reads; }
        $original($log);
    }, 1);
}
// Identical fixed warmup, excluded from the measured workload and sampler window.
atDepth($depth, 100_000);
$beforeCpu = cpuNs(getrusage());
$start = hrtime(true);
$sampler?->start();
$workStart = hrtime(true);
$checksum = atDepth($depth, $iterations);
$workEnd = hrtime(true);
$sampler?->stop();
$batch = $sampler?->flush();
$end = hrtime(true);
$afterCpu = cpuNs(getrusage());
$failures = $sampler?->failureCount() ?? 0;
$weight = $batch?->eventCount() ?? 0;
$scope->detach(); $span->end(); $provider->shutdown();
$result = [
    'mode' => $mode, 'hz' => $hz, 'depth' => $depth, 'iterations' => $iterations,
    'checksum' => $checksum, 'work_wall_ns' => $workEnd - $workStart,
    'total_wall_ns' => $end - $start, 'total_cpu_ns' => $afterCpu - $beforeCpu,
    'weight' => $weight, 'callbacks' => $callbacks, 'context_reads' => $reads,
    'failures' => $failures, 'stacks' => count($batch?->samples ?? []),
];
echo json_encode($result, JSON_THROW_ON_ERROR), "\n";
exit($failures === 0 && ($mode === 'off' || $weight > 0) ? 0 : 1);
