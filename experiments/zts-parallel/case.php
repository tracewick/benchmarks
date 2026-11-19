<?php

declare(strict_types=1);

require __DIR__ . '/probe.php';

$mode = $argv[1] ?? 'native';
$event = $argv[2] ?? 'wall';
$scenario = $argv[3] ?? 'concurrent';
$wire = $argv[4] ?? 'json';
$actors = ['alpha', 'beta', 'gamma', 'delta'];
$rows = [];
$threadCounts = [];
$cycles = $scenario === 'churn' ? 20 : 1;
$sequences = $scenario === 'reuse' ? 25 : 1;
$caught = [];
for ($cycle = 0; $cycle < $cycles; ++$cycle) {
    $runtimes = [];
    $futures = [];
    $workers = $scenario === 'idle-cpu' ? 2 : ($scenario === 'one' ? 1 : 4);
    for ($i = 0; $i < $workers; ++$i) {
        $runtimes[] = new parallel\Runtime(__DIR__ . '/probe.php');
    }
    for ($sequence = 0; $sequence < $sequences; ++$sequence) {
        foreach ($runtimes as $i => $runtime) {
            $futures[$i] = $runtime->run(static function ($m, $e, $a, $ms, $sleep, $shutdown, $wire) {
                $result = probeTask($m, $e, $a, $ms, $sleep, $shutdown);
                return $wire === 'array' ? $result : json_encode($result, JSON_THROW_ON_ERROR);
            }, [$scenario === 'parent-only' ? 'off' : $mode, $event, $actors[$i],
                $scenario === 'reuse' || $scenario === 'churn' ? 30 : 300,
                $scenario === 'idle-cpu' && $i === 0, $scenario === 'shutdown', $wire]);
        }
        if ($scenario === 'concurrent' || $scenario === 'parent-only') {
            $parent = new ProbeSession($mode, $event, 'parent');
            $rows[] = $parent->run(300, false);
            unset($parent);
        }
        foreach ($futures as $future) {
            $value = $future->value();
            $rows[] = $wire === 'array' ? $value : json_decode($value, true, flags: JSON_THROW_ON_ERROR);
        }
    }
    foreach ($runtimes as $runtime) {
        $runtime->close();
    }
    unset($futures, $future, $runtimes, $runtime);
    gc_collect_cycles();
    $status = file_get_contents('/proc/self/status');
    preg_match('/^Threads:\s+(\d+)/m', $status, $matches);
    $threadCounts[] = (int) ($matches[1] ?? 0);
}

$spool = [];
if (is_dir('/output/spool')) {
    $iterator = new RecursiveIteratorIterator(new RecursiveDirectoryIterator('/output/spool', FilesystemIterator::SKIP_DOTS));
    foreach ($iterator as $file) {
        if (!$file->isFile() || !str_ends_with($file->getFilename(), '.spool')) {
            continue;
        }
        $wire = Tracewick\Sink\SpoolFile::fromBytes(file_get_contents($file->getPathname()));
        $parts = (new Tracewick\Encoder\CompactStacksCodec())->decode($wire->payload);
        $markers = [];
        foreach ($parts->stacks as $stack) {
            foreach ($stack->frameIds as $id) {
                $name = $parts->frames[$id]->function ?? '';
                if (str_starts_with($name, 'probe')) {
                    $markers[$name] = ($markers[$name] ?? 0) + $stack->count;
                }
            }
        }
        $spool[] = ['labels' => $wire->labels, 'bytes' => $file->getSize(), 'format' => $wire->format,
            'markers' => $markers,
            'events' => array_sum(array_map(static fn($stack) => $stack->count, $parts->stacks))];
    }
}
echo json_encode(['php' => PHP_VERSION, 'zts' => PHP_ZTS, 'excimer' => phpversion('excimer'),
    'parallel' => phpversion('parallel'), 'mode' => $mode, 'event' => $event,
    'scenario' => $scenario, 'pid' => getmypid(), 'rows' => $rows, 'spool' => $spool,
    'threads_after_close' => $threadCounts, 'caught' => $caught], JSON_THROW_ON_ERROR) . "\n";
