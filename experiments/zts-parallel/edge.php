<?php

declare(strict_types=1);

require __DIR__ . '/probe.php';
$mode = $argv[1] ?? 'native';
$kind = $argv[2] ?? 'exception';
$ready = new parallel\Channel();
$runtime = new parallel\Runtime(__DIR__ . '/probe.php');
$future = $runtime->run(static function ($mode, $kind, $ready): string {
    $session = new ProbeSession($mode, 'wall', 'alpha');
    if ($session->native !== null) {
        $session->native->start();
    } else {
        $session->profiler->start(['actor' => 'alpha']);
    }
    $ready->send('profiling-started');
    try {
        probeAlpha($kind === 'kill' ? 5000 : 100, false);
        throw new RuntimeException('expected-worker-exception');
    } finally {
        $session->stop();
    }
}, [$mode, $kind, $ready]);
$started = $ready->recv();
if ($kind === 'kill') {
    usleep(20_000);
    $runtime->kill();
}
$caught = null;
try {
    $future->value();
} catch (Throwable $error) {
    $caught = ['class' => $error::class, 'message' => $error->getMessage()];
}
$reused = null;
if ($kind === 'exception') {
    $reused = $runtime->run(static fn(): int => 42)->value();
    $runtime->close();
}
unset($future, $runtime, $ready);
gc_collect_cycles();
preg_match('/^Threads:\s+(\d+)/m', file_get_contents('/proc/self/status'), $matches);
echo json_encode(['mode' => $mode, 'kind' => $kind, 'started' => $started,
    'caught' => $caught, 'reused' => $reused, 'threads_after' => (int) ($matches[1] ?? 0)],
    JSON_THROW_ON_ERROR) . "\n";
