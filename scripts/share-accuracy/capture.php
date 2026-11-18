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

function shareAlpha(int $durationNs): void
{
    $until = hrtime(true) + $durationNs;
    while (hrtime(true) < $until) {}
}

function shareBeta(int $durationNs, bool $sleep): void
{
    if ($sleep) {
        usleep((int) ceil($durationNs / 1_000));
        return;
    }
    $until = hrtime(true) + $durationNs;
    while (hrtime(true) < $until) {}
}

final class ShareSink implements Sink
{
    public array $events = ['alpha' => 0, 'beta' => 0, 'other' => 0];
    public function __construct(private readonly SpoolSink $spool) {}
    public function send(Profile $profile): Delivery
    {
        foreach ($profile->stacks as $stack) {
            $markers = [];
            foreach ($stack->frameIds as $id) {
                $name = $profile->frames[$id]->name();
                if ($name === 'shareAlpha') { $markers['alpha'] = true; }
                if ($name === 'shareBeta') { $markers['beta'] = true; }
            }
            if (count($markers) > 1) { throw new RuntimeException('Nested phase markers'); }
            $phase = array_key_first($markers) ?? 'other';
            $this->events[$phase] += $stack->count;
        }
        return $this->spool->send($profile);
    }
}

$spec = json_decode(file_get_contents($argv[1]), true, flags: JSON_THROW_ON_ERROR);
$out = $argv[2];
if (!extension_loaded('excimer')) { throw new RuntimeException('Excimer is required for this probe'); }
mt_srand($spec['seed']);
// Warm up both functions before the measured/profiled region.
shareAlpha(500_000_000);
shareBeta(500_000_000, $spec['sleep_beta']);
$sink = new ShareSink(new SpoolSink($spec['application'], new SpoolConfig($out . '/spool')));
$profiler = new UnitOfWorkProfiler(
    new ExcimerSampler(new SamplerConfig(periodNs: $spec['period_ns'], maxSamples: 1_000)),
    $sink,
    new ProfilerConfig(sampleRate: 1.0),
);
$elapsed = ['alpha' => 0, 'beta' => 0];
$cycles = [];
$profiler->start();
$started = hrtime(true);
do {
    $cycle = mt_rand(20_000, 80_000) * 1_000;
    $alpha = intdiv($cycle * $spec['alpha_percent'], 100);
    $order = mt_rand(0, 1) === 0 ? ['alpha', 'beta'] : ['beta', 'alpha'];
    $measured = [];
    foreach ($order as $phase) {
        $before = hrtime(true);
        if ($phase === 'alpha') { shareAlpha($alpha); }
        else { shareBeta($cycle - $alpha, $spec['sleep_beta']); }
        // The oracle reads elapsed wall time, never the sampler or native log.
        $duration = hrtime(true) - $before;
        $elapsed[$phase] += $duration;
        $measured[$phase] = $duration;
    }
    $cycles[] = ['requested_ns' => $cycle, 'order' => $order, 'elapsed_ns' => $measured];
} while (hrtime(true) - $started < $spec['duration_ns']);
$workNs = hrtime(true) - $started;
$profiler->stop();
$profiler->flush();
$d = $profiler->diagnostics();
$result = [
    'spec' => $spec,
    'elapsed_ns' => $elapsed,
    'work_ns' => $workNs,
    'source_events' => $sink->events,
    'diagnostics' => get_object_vars($d),
    'cycles' => $cycles,
    'runtime' => ['php' => PHP_VERSION, 'excimer' => phpversion('excimer'),
        'jit' => ini_get('opcache.jit'), 'opcache_cli' => ini_get('opcache.enable_cli')],
];
file_put_contents($out . '/oracle.json', json_encode($result, JSON_PRETTY_PRINT | JSON_THROW_ON_ERROR) . "\n");
if ($d->collectedProfiles !== 1 || $d->deliveredProfiles !== 1 || $d->swallowedErrors !== 0
    || $d->droppedProfiles !== 0 || $d->failedProfiles !== 0 || $d->samplerFailures !== 0
    || $d->inactiveSampler !== null) {
    throw new RuntimeException('Unexpected profiler diagnostics');
}
