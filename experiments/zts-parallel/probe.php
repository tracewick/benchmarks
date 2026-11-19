<?php

declare(strict_types=1);

require '/core/vendor/autoload.php';

use Tracewick\Profile\Profile;
use Tracewick\Profile\Labels;
use Tracewick\Runtime\ContinuousProfiler;
use Tracewick\Runtime\ContinuousProfilerConfig;
use Tracewick\Runtime\ProfilerConfig;
use Tracewick\Runtime\UnitOfWorkProfiler;
use Tracewick\Sampler\EventType;
use Tracewick\Sampler\SamplerConfig;
use Tracewick\Sink\Sink;
use Tracewick\Sink\SpoolSink;
use Tracewick\Transport\Delivery;
use Tracewick\Transport\SpoolConfig;

function probeSpin(int $milliseconds, bool $sleep): int
{
    if ($sleep) {
        usleep($milliseconds * 1000);
        return 1;
    }
    $until = hrtime(true) + $milliseconds * 1_000_000;
    $sum = 0;
    while (hrtime(true) < $until) {
        $sum = ($sum + 1) % 1000003;
    }
    return $sum;
}

function probeAlpha(int $ms, bool $sleep): int { return probeSpin($ms, $sleep); }
function probeBeta(int $ms, bool $sleep): int { return probeSpin($ms, $sleep); }
function probeGamma(int $ms, bool $sleep): int { return probeSpin($ms, $sleep); }
function probeDelta(int $ms, bool $sleep): int { return probeSpin($ms, $sleep); }
function probeParent(int $ms, bool $sleep): int { return probeSpin($ms, $sleep); }

function probeTid(): string
{
    return basename((string) readlink('/proc/thread-self'));
}

final class ProbeSink implements Sink
{
    public int $events = 0;
    public int $profiles = 0;
    public array $markers = [];
    public array $labels = [];
    private SpoolSink $spool;

    public function __construct(private string $actor)
    {
        $this->spool = new SpoolSink('zts-probe', new SpoolConfig('/output/spool'));
    }

    public function send(Profile $profile): Delivery
    {
        $this->events += $profile->eventCount();
        ++$this->profiles;
        $this->labels[] = $profile->labels->toArray();
        foreach ($profile->stacks as $stack) {
            foreach ($profile->framesOf($stack) as $frame) {
                if ($frame->function !== null && str_starts_with($frame->function, 'probe')) {
                    $this->markers[$frame->function] = ($this->markers[$frame->function] ?? 0) + $stack->count;
                }
            }
        }
        file_put_contents('/output/' . $this->actor . '-' . hrtime(true) . '.pprof',
            (new Tracewick\Encoder\PprofEncoder())->encode($profile));
        return $this->spool->send($profile);
    }
}

final class ProbeSession
{
    public ?ExcimerProfiler $native = null;
    public UnitOfWorkProfiler|ContinuousProfiler|null $profiler = null;
    public ?ProbeSink $sink = null;
    public int $events = 0;
    public int $callbacks = 0;
    public array $markers = [];
    public array $callbackActors = [];
    public string $tid;

    public function __construct(public string $mode, public string $event, public string $actor)
    {
        $this->tid = probeTid();
        $GLOBALS['probe_actor'] = $actor;
        if ($mode === 'native') {
            $this->native = new ExcimerProfiler();
            $this->native->setPeriod(0.001);
            $this->native->setEventType($event === 'cpu' ? EXCIMER_CPU : EXCIMER_REAL);
            $this->native->setMaxDepth(128);
            $this->native->setFlushCallback(function (ExcimerLog $log): void {
                ++$this->callbacks;
                $this->callbackActors[$GLOBALS['probe_actor'] ?? 'missing'] = true;
                $this->events += $log->getEventCount();
                foreach ($log as $entry) {
                    foreach ($entry->getTrace() as $frame) {
                        $name = $frame['function'] ?? '';
                        if (str_starts_with($name, 'probe')) {
                            $this->markers[$name] = ($this->markers[$name] ?? 0) + $entry->getEventCount();
                        }
                    }
                }
            }, 16);
        } elseif ($mode !== 'off') {
            $this->sink = new ProbeSink($actor);
            $sampler = new SamplerConfig(periodNs: 1_000_000,
                eventType: $event === 'cpu' ? EventType::Cpu : EventType::Wall, maxSamples: 16,
                projectRoot: '/probe');
            $this->profiler = $mode === 'continuous'
                ? ContinuousProfiler::create($this->sink,
                    new ContinuousProfilerConfig('zts-probe', new Labels(['actor' => $actor])), $sampler)
                : UnitOfWorkProfiler::create($this->sink, new ProfilerConfig(sampleRate: 1.0), $sampler);
        }
    }

    public function run(int $ms, bool $sleep, bool $shutdown = false): array
    {
        if ($shutdown && $this->profiler !== null) {
            $this->profiler->registerShutdown();
        }
        if ($this->native !== null) {
            $this->native->start();
        } elseif ($this->profiler instanceof UnitOfWorkProfiler) {
            $this->profiler->start(['actor' => $this->actor]);
        } else {
            $this->profiler?->start();
        }
        $start = hrtime(true);
        $function = 'probe' . ucfirst($this->actor);
        $checksum = $function($ms, $sleep);
        if (!$shutdown) {
            $this->stop();
        }
        $end = hrtime(true);
        return $this->summary() + ['start_ns' => $start, 'end_ns' => $end,
            'work_wall_ns' => $end - $start, 'checksum' => $checksum];
    }

    public function stop(): void
    {
        if ($this->native !== null) {
            $this->native->stop();
            $this->native->flush();
        } else {
            $this->profiler?->stop();
            $this->profiler?->flush();
        }
    }

    public function summary(): array
    {
        return ['actor' => $this->actor, 'tid' => $this->tid, 'mode' => $this->mode,
            'events' => $this->sink?->events ?? $this->events,
            'markers' => $this->sink?->markers ?? $this->markers,
            'profiles' => $this->sink?->profiles ?? 0, 'labels' => $this->sink?->labels ?? [],
            'callbacks' => $this->callbacks, 'callback_actors' => array_keys($this->callbackActors),
            'diagnostics' => $this->profiler?->diagnostics()];
    }
}

function probeTask(string $mode, string $event, string $actor, int $ms, bool $sleep, bool $shutdown): array
{
    // One actual profiler per interpreter; reused by subsequent tasks in this Runtime.
    static $session;
    $session ??= new ProbeSession($mode, $event, $actor);
    return $session->run($ms, $sleep, $shutdown);
}
