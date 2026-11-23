<?php

declare(strict_types=1);
require __DIR__ . '/Probe.php';

use OpenTelemetry\API\Trace\Span;
use OpenTelemetry\API\Trace\SpanContext;
use OpenTelemetry\SDK\Trace\Sampler\AlwaysOffSampler;

function spin(): void {
    $end = hrtime(true) + 24_000_000;
    while (hrtime(true) < $end) { hash('sha256', 'sample'); }
}
function parentWork(): void { spin(); }
function childWork(): void { spin(); }
function emptyWork(): void { spin(); }
function remoteWork(): void { spin(); }
function unsampledWork(): void { spin(); }
function fiberWork(): void { spin(); }

function change(Probe $probe, Closure $operation): mixed {
    $probe->beforeChange();
    $result = $operation();
    $probe->afterChange();
    return $result;
}

function checkWindow(string $mode, bool $eligible, int $limit): array {
    $tracer = experimentProvider()->getTracer('window');
    $off = experimentProvider(new AlwaysOffSampler())->getTracer('off');
    $remote = Span::wrap(SpanContext::createFromRemoteParent(str_repeat('a', 32), str_repeat('b', 16), 1));
    $expected = ['emptyWork' => '', 'remoteWork' => '', 'fiberWork' => ''];
    $wrong = $seen = [];
    $observer = static function ($trace, $key, $weight) use (&$expected, &$wrong, &$seen, $eligible) {
        foreach ($trace as $frame) {
            $phase = $frame['function'] ?? '';
            if (!isset($expected[$phase])) { continue; }
            $seen[$phase][$key === '' ? 'empty' : 'linked'] = true;
            if ($key !== '' && (!$eligible || $key !== $expected[$phase] || $weight > 1)) {
                $wrong[] = $phase;
            }
            break;
        }
    };
    $p = new Probe($mode, 1000, 48, $eligible, $observer, $limit);
    $total = 0;
    for ($unit = 0; $unit < 2; ++$unit) {
        $p->native->start();
        emptyWork();
        $r = change($p, $remote->activate(...)); remoteWork();
        $parent = $tracer->spanBuilder('local')->startSpan();
        $s = change($p, $parent->activate(...));
        $expected['parentWork'] = Probe::readToken(); parentWork();
        $child = $tracer->spanBuilder('child')->startSpan();
        $c = change($p, $child->activate(...));
        $expected['childWork'] = Probe::readToken(); $child->end(); childWork();
        $p->native->stop();
        $total += array_sum($p->drain());
        $p->native->start();
        change($p, $c->detach(...)); parentWork();
        $c = change($p, $child->activate(...)); childWork(); change($p, $c->detach(...));
        usleep(13000);
        if (!$eligible) { (new Fiber(fiberWork(...)))->start(); }
        change($p, $s->detach(...)); $parent->end(); remoteWork(); change($p, $r->detach(...));
        $span = $off->spanBuilder('unsampled')->startSpan();
        $s = change($p, $span->activate(...));
        $expected['unsampledWork'] = Probe::readToken(); unsampledWork();
        change($p, $s->detach(...)); $span->end(); emptyWork();
        $p->native->stop();
        $total += array_sum($p->drain());
        if ($p->drain() !== []) { throw new LogicException('Repeated flush produced weight'); }
    }
    $pass = ($mode === 'late' ? count($wrong) > 0 : !$wrong)
        && $total === $p->nativeWeight && $total === $p->weight && $p->coalesced > 0;
    foreach (array_keys($expected) as $phase) {
        if ($eligible && $phase === 'fiberWork') { continue; }
        $pass = $pass && isset($seen[$phase]);
        if ($eligible && $mode !== 'late' && $limit === 512 && $expected[$phase] !== '') {
            $pass = $pass && isset($seen[$phase]['linked']);
        }
    }
    if ($limit === 4) { $pass = $pass && $p->overflow > 0; }
    return compact('mode','eligible','limit','total','pass','seen') +
        ['wrong' => count($wrong), 'coalesced_weight' => $p->coalesced, 'overflow' => $p->overflow];
}

$results = [];
foreach (['history','deferred','late'] as $mode) {
    $results[] = checkWindow($mode, true, 512);
    if ($mode !== 'late') {
        $results[] = checkWindow($mode, false, 512);
        $results[] = checkWindow($mode, true, 4);
    }
}
echo json_encode($results, JSON_PRETTY_PRINT), "\n";
exit(in_array(false, array_column($results,'pass'), true) ? 1 : 0);
