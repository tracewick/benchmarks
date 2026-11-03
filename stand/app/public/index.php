<?php

declare(strict_types=1);

use Tracewick\Profile\Labels;
use Tracewick\Runtime\ProfilerConfig;
use Tracewick\Runtime\UnitOfWorkProfiler;
use Tracewick\Sink\SpoolSink;
use Tracewick\Transport\SpoolConfig;

require dirname(__DIR__) . '/vendor/autoload.php';

$path = parse_url($_SERVER['REQUEST_URI'] ?? '/', PHP_URL_PATH) ?: '/';
$method = $_SERVER['REQUEST_METHOD'] ?? 'GET';

$enabledRaw = getenv('TRACEWICK_ENABLED');
$profilingEnabled = $enabledRaw === false || $enabledRaw === ''
    ? true
    : !in_array(strtolower((string) $enabledRaw), ['0', 'false', 'off', 'no'], true);

if ($path === '/health') {
    header('Content-Type: application/json');
    echo json_encode([
        'ok' => true,
        'excimer' => extension_loaded('excimer'),
        'tracewick' => class_exists(UnitOfWorkProfiler::class),
        'profiling_enabled' => $profilingEnabled,
        'sample_rate' => (float) (getenv('TRACEWICK_SAMPLE_RATE') ?: '0.1'),
    ], JSON_THROW_ON_ERROR);
    exit;
}

$spoolDir = getenv('TRACEWICK_SPOOL_DIR') ?: '/var/spool/tracewick';
$sampleRate = (float) (getenv('TRACEWICK_SAMPLE_RATE') ?: '0.1');
$service = getenv('TRACEWICK_SERVICE') ?: 'benchmarks-workload';
$envLabel = getenv('TRACEWICK_ENV') ?: 'bench';
$busyMs = max(0, (int) (getenv('WORK_BUSY_MS') ?: '25'));
$sleepMs = max(0, (int) (getenv('WORK_SLEEP_MS') ?: '10'));

$route = $path === '/' || $path === '/work' ? 'work' : 'other';
$profiler = null;

if ($profilingEnabled) {
    $profiler = UnitOfWorkProfiler::create(
        new SpoolSink($service, new SpoolConfig($spoolDir)),
        new ProfilerConfig(
            new Labels([
                'service' => $service,
                'env' => $envLabel,
                'runtime' => 'fpm',
            ]),
            sampleRate: $sampleRate,
        ),
    );
    $profiler->start(['route' => $route, 'method' => $method]);
    $profiler->registerShutdown();
}

if ($route !== 'work') {
    http_response_code(404);
    header('Content-Type: application/json');
    echo json_encode(['error' => 'not_found', 'path' => $path], JSON_THROW_ON_ERROR);
    exit;
}

$started = hrtime(true);
busyWork($busyMs);
if ($sleepMs > 0) {
    usleep($sleepMs * 1000);
}
$elapsedMs = (hrtime(true) - $started) / 1_000_000;

header('Content-Type: application/json');
echo json_encode([
    'ok' => true,
    'route' => $route,
    'busy_ms' => $busyMs,
    'sleep_ms' => $sleepMs,
    'elapsed_ms' => round($elapsedMs, 3),
    'profiling_enabled' => $profilingEnabled,
    'sample_rate' => $sampleRate,
    'spool_dir' => $spoolDir,
], JSON_THROW_ON_ERROR);

/**
 * Burn roughly $milliseconds of CPU so wall/cpu samples have something to catch.
 */
function busyWork(int $milliseconds): void
{
    if ($milliseconds <= 0) {
        return;
    }

    $deadline = hrtime(true) + ($milliseconds * 1_000_000);
    $x = 0.0;
    while (hrtime(true) < $deadline) {
        $x += sin($x + 1.2345);
        if ($x > 1_000_000.0) {
            $x = 0.0;
        }
    }
}
