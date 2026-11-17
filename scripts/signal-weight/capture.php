<?php

declare(strict_types=1);

require '/workspace/tracewick/vendor/autoload.php';

use Tracewick\Profile\Profile;
use Tracewick\Runtime\ProfilerConfig;
use Tracewick\Runtime\UnitOfWorkProfiler;
use Tracewick\Sampler\ExcimerSampler;
use Tracewick\Sampler\SamplerConfig;
use Tracewick\Sink\Sink;
use Tracewick\Sink\SpoolSink;
use Tracewick\Transport\Delivery;
use Tracewick\Transport\SpoolConfig;

final class WeightCapture implements Sink
{
    public int $events = 0;
    public function __construct(private readonly SpoolSink $spool) {}
    public function send(Profile $profile): Delivery
    {
        $this->events = array_sum(array_map(static fn($stack): int => $stack->count, $profile->stacks));
        return $this->spool->send($profile);
    }
}

function signalWork(): void
{
    $until = hrtime(true) + 30_000_000;
    while (hrtime(true) < $until) {}
}

function capture(string $runtime, string $run): array
{
    static $instances = [];
    $out = '/workspace/signal-verification/output';
    $dir = "$out/$runtime-$run";
    if (!isset($instances[$dir])) {
        if (!is_dir($dir)) {
            mkdir($dir, 0777, true);
        }
        $sampler = new ExcimerSampler(new SamplerConfig(periodNs: 1_000_000, maxSamples: 100_000));
        $sink = new WeightCapture(new SpoolSink("signal-$runtime-$run", new SpoolConfig($dir)));
        $profiler = new UnitOfWorkProfiler($sampler, $sink, new ProfilerConfig(sampleRate: 1.0));
        $instances[$dir] = [$sampler, $sink, $profiler];
    }
    [$sampler, $sink, $profiler] = $instances[$dir];
    $profiler->start(['runtime' => $runtime, 'route' => 'signal']);
    signalWork();
    // Freeze sampling before reading the independent native event-count oracle.
    $sampler->stop();
    $native = (new ReflectionProperty($sampler, 'profiler'))->getValue($sampler);
    $expected = $native->getLog()->getEventCount();
    $profiler->stop();
    $profiler->flush();
    if ($expected <= 0 || $expected !== $sink->events) {
        throw new RuntimeException("Native/profile mismatch: $expected vs {$sink->events}");
    }
    $result = ['runtime' => $runtime, 'run' => $run, 'pid' => getmypid(), 'native_events' => $expected, 'profile_events' => $sink->events, 'period_ns' => 1_000_000];
    file_put_contents("$dir/captures.jsonl", json_encode($result, JSON_THROW_ON_ERROR) . "\n", FILE_APPEND);
    return $result;
}
