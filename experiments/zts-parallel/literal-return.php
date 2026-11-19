<?php

declare(strict_types=1);

require __DIR__ . '/literal-bootstrap.php';
$runtimes = $futures = $rows = [];
$wire = $argv[1] ?? 'array';
for ($i = 0; $i < 4; ++$i) {
    $runtimes[$i] = new parallel\Runtime(__DIR__ . '/literal-bootstrap.php');
    $task = $wire === 'array'
        ? static fn(): array => literalTask()
        : static fn(): string => json_encode(literalTask(), JSON_THROW_ON_ERROR);
    $futures[$i] = $runtimes[$i]->run($task);
}
$rows[] = (new LiteralFixture())->payload();
foreach ($futures as $future) {
    $rows[] = $wire === 'array' ? $future->value()
        : json_decode($future->value(), true, flags: JSON_THROW_ON_ERROR);
}
foreach ($runtimes as $runtime) {
    $runtime->close();
}
unset($futures, $future, $runtimes, $runtime);
gc_collect_cycles();
echo json_encode($rows, JSON_THROW_ON_ERROR) . "\n";
