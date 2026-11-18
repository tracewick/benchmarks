<?php

declare(strict_types=1);

require __DIR__ . '/bootstrap.php';

use OpenTelemetry\API\Trace\Span;
use OpenTelemetry\API\Trace\SpanContext;
use OpenTelemetry\SDK\Trace\Sampler\AlwaysOffSampler;
use OpenTelemetry\SDK\Trace\SpanExporter\InMemoryExporter;
use OpenTelemetry\SDK\Trace\SpanProcessor\SimpleSpanProcessor;
use Tracewick\Sampler\ExcimerSampler;
use Tracewick\Sampler\SamplerConfig;
use Tracewick\Runtime\ProfilerConfig;
use Tracewick\Runtime\UnitOfWorkProfiler;
use Tracewick\Profile\Profile;
use Tracewick\Sink\Sink;
use Tracewick\Transport\Delivery;

function sdkWork(): void
{
    $deadline = hrtime(true) + 35_000_000;
    while (hrtime(true) < $deadline) {
        hash('sha256', 'real-sdk-context');
    }
}
function sdkNone(): void { sdkWork(); }
function sdkParent(): void { sdkWork(); }
function sdkChild(): void { sdkWork(); }
function sdkRestored(): void { sdkWork(); }
function sdkEndedActive(): void { sdkWork(); }
function sdkUnsampled(): void { sdkWork(); }
function sdkRemote(): void { sdkWork(); }
function sdkLocalChild(): void { sdkWork(); }
function sdkAfterDetach(): void { sdkWork(); }

$state = (object) [
    'depth' => 0, 'nativeWeight' => 0, 'mismatches' => 0, 'multiEntryLogs' => 0,
    'exportsInCallback' => 0, 'autoloads' => [], 'warnings' => [], 'phases' => [], 'expected' => [],
    'sinkInCallback' => 0, 'deliveredWeight' => 0,
];
$exporter = new class($state) extends InMemoryExporter {
    public function __construct(private object $state) { parent::__construct(); }
    protected function doExport(iterable $spans): bool
    {
        if ($this->state->depth > 0) { ++$this->state->exportsInCallback; }
        return parent::doExport($spans);
    }
};
$provider = experimentProvider(processors: [new SimpleSpanProcessor($exporter)]);
$offProvider = experimentProvider(new AlwaysOffSampler());
$tracer = $provider->getTracer('callback-preflight');
$offTracer = $offProvider->getTracer('callback-preflight-off');
$remote = Span::wrap(SpanContext::createFromRemoteParent(str_repeat('3', 32), str_repeat('4', 16), 1));
$pair = static fn($span): array => [$span->getContext()->getTraceId(), $span->getContext()->getSpanId()];
$state->expected = [
    'sdkNone' => null, 'sdkParent' => null, 'sdkChild' => null,
    'sdkRestored' => null, 'sdkEndedActive' => null,
    'sdkUnsampled' => null, 'sdkRemote' => null,
    'sdkLocalChild' => null, 'sdkAfterDetach' => null,
];
// Prepare only the optional reader path; no manual core-type preload is used.
experimentContext();
$sampler = new ExcimerSampler(new SamplerConfig(periodNs: 1_000_000, maxDepth: 48, maxSamples: 1));
$clock = new class implements Tracewick\Clock\Clock {
    public int $now = 1_000_000_000_000_000_000;
    public function nowNs(): int { return $this->now; }
};
$runtime = null;
if (in_array('--rotation', $argv, true)) {
    $sink = new class($state) implements Sink {
        public function __construct(private object $state) {}
        public function send(Profile $profile): Delivery
        {
            if ($this->state->depth > 0) { ++$this->state->sinkInCallback; }
            foreach ($profile->stacks as $stack) { $this->state->deliveredWeight += $stack->count; }
            return Delivery::delivered();
        }
    };
    $runtime = new UnitOfWorkProfiler($sampler, $sink,
        new ProfilerConfig(sampleRate: 1.0, maxProfileDurationSeconds: 1), clock: $clock);
}
$native = (new ReflectionProperty($sampler, 'profiler'))->getValue($sampler);
$original = (new ReflectionMethod($sampler, 'onNativeFlush'))->getClosure($sampler);
$marker = getenv('OTEL_PROBE_MARKERS') === '1' ? fopen('php://fd/3', 'w') : null;
$autoloadObserver = static function (string $class) use ($state): void {
    if ($state->depth > 0) { $state->autoloads[$class] = true; }
};
spl_autoload_register($autoloadObserver, true, true);
set_error_handler(static function (int $type, string $message) use ($state): bool {
    $state->warnings[] = ['callback' => $state->depth > 0, 'message' => $message];
    return true;
});
$native->setFlushCallback(static function (ExcimerLog $log) use ($state, $original, $marker): void {
    if (is_resource($marker)) { fwrite($marker, "OTEL_CB_BEGIN\n"); }
    ++$state->depth;
    try {
        $state->nativeWeight += $log->getEventCount();
        if (count($log) > 1) { ++$state->multiEntryLogs; }
        $actual = count($log) === 1 ? experimentContext() : null;
        foreach ($log as $entry) {
            foreach ($entry->getTrace() as $frame) {
                $phase = $frame['function'] ?? '';
                if (array_key_exists($phase, $state->expected)) {
                    $state->phases[$phase] = ($state->phases[$phase] ?? 0) + $entry->getEventCount();
                    if ($actual !== $state->expected[$phase]) { ++$state->mismatches; }
                    break;
                }
            }
        }
        $original($log);
    } finally {
        --$state->depth;
        if (is_resource($marker)) { fwrite($marker, "OTEL_CB_END\n"); }
    }
}, 1);

if ($runtime !== null) { $runtime->start(); } else { $sampler->start(); }
sdkNone();
$parent = $tracer->spanBuilder('parent')->startSpan();
$state->expected['sdkParent'] = $state->expected['sdkRestored'] = $pair($parent);
$parentScope = $parent->activate();
if ($runtime !== null) { $clock->now += 2_000_000_000; }
sdkParent();
$child = $tracer->spanBuilder('child')->startSpan();
$state->expected['sdkChild'] = $state->expected['sdkEndedActive'] = $pair($child);
$childScope = $child->activate(); sdkChild();
$child->end(); sdkEndedActive(); $childScope->detach();
sdkRestored(); $parentScope->detach(); $parent->end();
$unsampled = $offTracer->spanBuilder('unsampled')->startSpan();
$state->expected['sdkUnsampled'] = $pair($unsampled);
$offScope = $unsampled->activate(); sdkUnsampled(); $offScope->detach(); $unsampled->end();
$remoteScope = $remote->activate(); sdkRemote();
$localChild = $tracer->spanBuilder('local-child')->startSpan();
$state->expected['sdkLocalChild'] = $pair($localChild);
$localScope = $localChild->activate(); sdkLocalChild(); $localScope->detach(); $localChild->end();
sdkRemote(); $remoteScope->detach(); sdkAfterDetach();
if ($runtime !== null) {
    $runtime->stop(); $runtime->flush();
    $weight = $state->deliveredWeight;
} else {
    $sampler->stop(); $weight = $sampler->flush()->eventCount();
}
$emptyWeight = $sampler->flush()->eventCount();
spl_autoload_unregister($autoloadObserver);
restore_error_handler();
$result = [
    'php' => PHP_VERSION, 'excimer' => phpversion('excimer'),
    'recording_span_class' => get_debug_type($parent),
    'unsampled_span_class' => get_debug_type($unsampled),
    'unsampled_valid_local' => $unsampled->getContext()->isValid() && !$unsampled->getContext()->isRemote() && !$unsampled->getContext()->isSampled(),
    'native_weight' => $state->nativeWeight, 'batch_weight' => $weight, 'second_flush_weight' => $emptyWeight,
    'phases' => $state->phases, 'context_mismatches' => $state->mismatches,
    'callback_autoloads' => array_keys($state->autoloads), 'warnings' => $state->warnings,
    'exports_in_callback' => $state->exportsInCallback, 'exported_spans' => count($exporter->getSpans()),
    'multi_entry_logs' => $state->multiEntryLogs,
    'rotation_collected' => $runtime?->diagnostics()->collectedProfiles,
    'sink_in_callback' => $state->sinkInCallback,
];
$result['pass'] = $state->nativeWeight === $weight && $weight > 0 && $emptyWeight === 0
    && count($state->phases) === count($state->expected) && $state->mismatches === 0
    && $state->autoloads === [] && $state->warnings === [] && $state->exportsInCallback === 0
    && $result['exported_spans'] === 3 && $result['unsampled_valid_local'] && $state->multiEntryLogs === 0;
if ($runtime !== null) { $result['pass'] = $result['pass'] && $result['rotation_collected'] >= 2 && $state->sinkInCallback === 0; }
$provider->shutdown(); $offProvider->shutdown();
echo json_encode($result, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES), "\n";
exit($result['pass'] ? 0 : 1);
