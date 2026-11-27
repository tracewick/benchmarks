<?php

declare(strict_types=1);

require_once __DIR__ . '/../otel-callback/bootstrap.php';

use Tracewick\Sampler\ExcimerTraceConverter;
use Tracewick\Sampler\StackAggregator;
use Tracewick\Sampler\Frame;
use Tracewick\Sampler\Sample;

/** Isolated sequential harness. The caller owns every scope transition in an eligible window. */
final class Probe
{
    public ExcimerProfiler $native;
    private ExcimerTraceConverter $converter;
    private array $groups = [];
    private array $history = [];
    private array $pending = [];
    private ?string $token = null;
    private int $originLow;
    private int $originHigh;
    public int $callbacks = 0;
    public int $changes = 0;
    public int $nativeWeight = 0;
    public int $weight = 0;
    public int $coalesced = 0;
    public int $queuePeak = 0;
    public int $overflow = 0;

    public function __construct(
        private string $mode, int $hz, int $depth, private bool $eligible = true,
        private ?Closure $observer = null, private int $limit = 512,
    ) {
        class_exists(Frame::class);
        class_exists(Sample::class);
        $this->converter = new ExcimerTraceConverter(0, $depth, null);
        $this->groups[''] = new StackAggregator(512);
        $this->originLow = hrtime(true);
        $this->native = new ExcimerProfiler();
        $this->originHigh = hrtime(true);
        $this->native->setPeriod(1 / $hz);
        $this->native->setEventType(EXCIMER_REAL);
        $this->native->setMaxDepth($depth);
        $this->native->setFlushCallback($this->capture(...), in_array($mode, ['immediate', 'otel', 'deferred'], true) ? 1 : 10000);
        $this->afterChange();
        $this->changes = 0;
    }

    public function beforeChange(): void
    {
        $this->token = null;
        if ($this->mode === 'history' && $this->history !== []) {
            $i = array_key_last($this->history);
            $this->history[$i][1] = hrtime(true);
        }
    }

    public function afterChange(): void
    {
        ++$this->changes;
        if (!$this->eligible || !in_array($this->mode, ['history','deferred'], true)) {
            return;
        }
        $this->token = self::readToken();
        if ($this->mode === 'history') {
            if (count($this->history) >= $this->limit) {
                $this->history = [];
                ++$this->overflow;
            }
            $this->history[] = [hrtime(true), PHP_INT_MAX, $this->token];
        }
    }

    public static function readToken(): ?string
    {
        $pair = experimentContext();
        return $pair === null ? null : implode('/', $pair);
    }

    private function lookup(float $timestamp): ?string
    {
        $ns = (int) round($timestamp * 1e9);
        $earliest = $this->originLow + $ns - 1;
        $latest = $this->originHigh + $ns + 1;
        $lo = 0;
        $hi = count($this->history);
        while ($lo < $hi) {
            $mid = ($lo + $hi) >> 1;
            if ($this->history[$mid][0] < $earliest) {
                $lo = $mid + 1;
            } else {
                $hi = $mid;
            }
        }
        if ($lo === 0) {
            return null;
        }
        [, $end, $token] = $this->history[$lo - 1];
        return $latest < $end ? $token : null;
    }

    private function capture(ExcimerLog $log): void
    {
        ++$this->callbacks;
        if ($this->observer !== null) { $this->nativeWeight += $log->getEventCount(); }
        if ($this->mode === 'deferred' && count($log) === 1) {
            if (count($this->pending) < $this->limit) {
                $this->pending[] = [$log, $this->token];
                $this->queuePeak = max($this->queuePeak, count($this->pending));
                return;
            }
            ++$this->overflow;
        }
        $token = $this->eligible && ($this->mode === 'late' || ($this->mode === 'otel' && count($log) === 1))
            ? self::readToken() : null;
        $this->ingest($log, $token);
    }

    private function ingest(ExcimerLog $log, ?string $token): void
    {
        foreach ($log as $entry) {
            $weight = $entry->getEventCount();
            $this->weight += $weight;
            $key = $this->mode === 'history' ? $this->lookup($entry->getTimestamp()) : $token;
            if ($weight > 1) {
                $this->coalesced += $weight;
                $key = null;
            }
            $key ??= '';
            if (!isset($this->groups[$key]) && count($this->groups) >= 16) {
                $key = '';
            }
            $trace = $entry->getTrace();
            if ($this->observer !== null) {
                ($this->observer)($trace, $key, $weight);
            }
            $group = $this->groups[$key] ??= new StackAggregator(512);
            $this->converter->ingestEntry($trace, $weight, $group);
        }
    }

    /** Caller must stop sampling before draining. An active timer can append during traversal. */
    public function drain(): array
    {
        $this->native->flush();
        foreach ($this->pending as [$log, $token]) {
            $this->ingest($log, $token);
        }
        $this->pending = [];
        $weights = [];
        foreach ($this->groups as $key => $group) {
            foreach ($group->toSamples(0) as $sample) {
                $weights[$key] = ($weights[$key] ?? 0) + $sample->count;
            }
        }
        $this->groups = ['' => new StackAggregator(512)];
        return $weights;
    }
}
