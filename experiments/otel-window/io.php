<?php
declare(strict_types=1);

require __DIR__ . '/Probe.php';

$mode = $argv[1];
$provider = experimentProvider();
$parent = $provider->getTracer('io')->spanBuilder('parent')->startSpan();
$scope = $parent->activate();
$p = new Probe($mode, 1000, 48, limit: 4);
$marker = fopen('php://fd/3', 'w');
$original = (new ReflectionMethod($p, 'capture'))->getClosure($p);
$p->native->setFlushCallback(static function (ExcimerLog $log) use ($marker, $original): void {
    fwrite($marker, "OTEL_CB_BEGIN\n");
    try { $original($log); }
    finally { fwrite($marker, "OTEL_CB_END\n"); }
}, $mode === 'history' ? 8 : 1);
$p->native->start();
$end = hrtime(true) + 90_000_000;
while (hrtime(true) < $end) { hash('sha256', 'io'); }
$p->native->stop();
$weights = $p->drain();
if (array_sum($weights) < 1) { throw new LogicException('Missing weight'); }
$scope->detach(); $parent->end(); $provider->shutdown();
