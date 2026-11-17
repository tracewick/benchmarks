<?php

declare(strict_types=1);

// Process microbenchmark: no HTTP/capacity or final correlation-model claims.
$output = $argv[1] ?? throw new InvalidArgumentException('Output JSON path is required.');
$rounds = (int) ($argv[2] ?? 7);
$targetMs = (int) ($argv[3] ?? 500);
if ($rounds < 3 || $targetMs < 100) { throw new InvalidArgumentException('Use at least 3 rounds and 100 ms.'); }

function runWorker(string $mode, int $hz, int $depth, int $iterations): array
{
    $process = proc_open([
        'timeout', '15', PHP_BINARY, '-d', 'pcov.enabled=0', '-d', 'opcache.enable_cli=0',
        __DIR__ . '/worker.php', $mode, (string) $hz, (string) $depth, (string) $iterations,
    ], [0 => ['pipe', 'r'], 1 => ['pipe', 'w'], 2 => ['pipe', 'w']], $pipes);
    if (!is_resource($process)) { throw new RuntimeException('Cannot start worker.'); }
    fclose($pipes[0]);
    $stdout = stream_get_contents($pipes[1]); $stderr = stream_get_contents($pipes[2]);
    fclose($pipes[1]); fclose($pipes[2]);
    $exit = proc_close($process);
    if ($exit !== 0) { throw new RuntimeException("Worker $mode/$hz/$depth exited $exit: $stderr $stdout"); }
    return json_decode($stdout, true, flags: JSON_THROW_ON_ERROR);
}

$cpu = file_get_contents('/proc/cpuinfo');
preg_match('/model name\s*:\s*(.+)/', $cpu, $match);
$metadata = [
    'started_utc' => gmdate('c'), 'php' => PHP_VERSION, 'excimer' => phpversion('excimer'),
    'kernel' => php_uname('s') . ' ' . php_uname('r') . ' ' . php_uname('m'), 'cpu_model' => $match[1] ?? 'unknown',
    'memory_total' => preg_match('/MemTotal:\s*(.+)/', file_get_contents('/proc/meminfo'), $mem) ? $mem[1] : null,
    'cpu_max' => @file_get_contents('/sys/fs/cgroup/cpu.max'),
    'cpu_stat_before' => @file_get_contents('/sys/fs/cgroup/cpu.stat'),
    'pcov_enabled' => ini_get('pcov.enabled'), 'opcache_cli' => ini_get('opcache.enable_cli'),
    'sdk' => '1.16.1', 'api' => '1.11.0', 'context' => '1.6.0',
    'rounds' => $rounds, 'target_baseline_ms' => $targetMs, 'random_seed' => 20261117,
    'method' => 'Fixed iterations; randomized four-mode order within each round; separate PHP process per row. Total includes sampler start/stop/final flush. All modes have the same active SDK span. No strace or coverage.',
];
$calibration = runWorker('off', 100, 48, 1_000_000);
$iterations = max(1_000_000, (int) ceil(1_000_000 * $targetMs * 1_000_000 / $calibration['work_wall_ns']));
$rows = [];
mt_srand(20261117);
foreach ([48, 256] as $depth) {
    foreach ([100, 1000] as $hz) {
        for ($round = 1; $round <= $rounds; ++$round) {
            $modes = ['off', 'batched', 'immediate', 'otel']; shuffle($modes);
            foreach ($modes as $position => $mode) {
                $row = runWorker($mode, $hz, $depth, $iterations);
                $row['round'] = $round; $row['position'] = $position;
                if ($row['checksum'] !== $calibration['checksum'] && $row['iterations'] === $calibration['iterations']) {
                    throw new RuntimeException('Calibration checksum mismatch.');
                }
                $rows[] = $row;
                file_put_contents($output, json_encode(['metadata' => $metadata, 'calibration' => $calibration, 'rows' => $rows], JSON_PRETTY_PRINT) . "\n");
            }
        }
        echo "Completed depth=$depth hz=$hz ($rounds randomized rounds)\n";
    }
}
$checksums = array_unique(array_column($rows, 'checksum'));
if (count($checksums) !== 1) { throw new RuntimeException('Workload differs across rows.'); }
$metadata['finished_utc'] = gmdate('c');
$metadata['cpu_stat_after'] = @file_get_contents('/sys/fs/cgroup/cpu.stat');
file_put_contents($output, json_encode(['metadata' => $metadata, 'calibration' => $calibration, 'rows' => $rows], JSON_PRETTY_PRINT) . "\n");
echo 'Saved ', count($rows), " measured rows\n";
