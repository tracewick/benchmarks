<?php

declare(strict_types=1);

/**
 * Swoole HTTP server — same synthetic /work as FPM / RoadRunner.
 * ContinuousProfiler (process-level) + SpoolSink → shared spool → drain/agent.
 *
 * Sample rate does not apply: ContinuousProfiler is always-on when ENABLED=1.
 */

use Swoole\Http\Request;
use Swoole\Http\Response;
use Swoole\Http\Server;
use Swoole\Timer;
use Tracewick\Profile\Labels;
use Tracewick\Runtime\ContinuousProfiler;
use Tracewick\Runtime\ContinuousProfilerConfig;
use Tracewick\Sink\SpoolSink;
use Tracewick\Transport\SpoolConfig;

require __DIR__ . '/vendor/autoload.php';
require __DIR__ . '/src/SyntheticWork.php';

$enabledRaw = getenv('TRACEWICK_ENABLED');
$profilingEnabled = $enabledRaw === false || $enabledRaw === ''
    ? true
    : !in_array(strtolower((string) $enabledRaw), ['0', 'false', 'off', 'no'], true);

$spoolDir = getenv('TRACEWICK_SPOOL_DIR') ?: '/var/spool/tracewick';
$spoolMaxFiles = max(1, (int) (getenv('TRACEWICK_SPOOL_MAX_FILES') ?: '500'));
$service = getenv('TRACEWICK_SERVICE') ?: 'benchmarks-workload';
$envLabel = getenv('TRACEWICK_ENV') ?: 'bench';
$busyMs = max(0, (int) (getenv('WORK_BUSY_MS') ?: '25'));
$sleepMs = max(0, (int) (getenv('WORK_SLEEP_MS') ?: '10'));
$stackDepth = max(0, (int) (getenv('WORK_STACK_DEPTH') ?: '0'));
$workerNum = max(1, (int) (getenv('SWOOLE_WORKER_NUM') ?: '4'));
$listenHost = getenv('SWOOLE_LISTEN_HOST') ?: '0.0.0.0';
$listenPort = max(1, (int) (getenv('SWOOLE_LISTEN_PORT') ?: '8080'));
$pulseMs = max(100, (int) (getenv('TRACEWICK_PULSE_MS') ?: '1000'));

$server = new Server($listenHost, $listenPort);
$server->set([
    'worker_num' => $workerNum,
    'enable_coroutine' => false,
    'max_request' => 0,
]);

/** @var array{profiler: ?ContinuousProfiler, timer: int|false} $workerState */
$workerState = ['profiler' => null, 'timer' => false];

$server->on('WorkerStart', static function (Server $server, int $workerId) use (
    &$workerState,
    $profilingEnabled,
    $spoolDir,
    $spoolMaxFiles,
    $service,
    $envLabel,
    $pulseMs,
): void {
    if (!$profilingEnabled) {
        return;
    }

    $profiler = ContinuousProfiler::create(
        new SpoolSink($service, new SpoolConfig($spoolDir, maxFiles: $spoolMaxFiles)),
        new ContinuousProfilerConfig(
            $service,
            new Labels([
                'service' => $service,
                'env' => $envLabel,
                'runtime' => 'swoole',
            ]),
        ),
    );
    $profiler->start();
    $profiler->registerShutdown();
    $workerState['profiler'] = $profiler;
    $workerState['timer'] = Timer::tick($pulseMs, static function () use ($profiler): void {
        $profiler->pulse();
    });
});

$server->on('WorkerStop', static function () use (&$workerState): void {
    if ($workerState['timer'] !== false) {
        Timer::clear((int) $workerState['timer']);
        $workerState['timer'] = false;
    }
    $profiler = $workerState['profiler'];
    if ($profiler instanceof ContinuousProfiler) {
        $profiler->stop();
        $workerState['profiler'] = null;
    }
});

$server->on('request', static function (Request $request, Response $response) use (
    $profilingEnabled,
    $spoolDir,
    $spoolMaxFiles,
    $busyMs,
    $sleepMs,
    $stackDepth,
    $workerNum,
): void {
    $path = $request->server['request_uri'] ?? '/';
    $method = strtoupper((string) ($request->server['request_method'] ?? 'GET'));
    $qPos = strpos($path, '?');
    if ($qPos !== false) {
        $path = substr($path, 0, $qPos);
    }

    $response->header('Content-Type', 'application/json');

    if ($path === '/health') {
        $response->end(json_encode([
            'ok' => true,
            'excimer' => extension_loaded('excimer'),
            'swoole' => extension_loaded('swoole'),
            'tracewick' => class_exists(ContinuousProfiler::class),
            'profiling_enabled' => $profilingEnabled,
            'profiler' => 'continuous',
            'spool_max_files' => $spoolMaxFiles,
            'work_stack_depth' => $stackDepth,
            'runtime' => 'swoole',
            'swoole_worker_num' => $workerNum,
        ], JSON_THROW_ON_ERROR));

        return;
    }

    $route = match ($path) {
        '/', '/work' => 'work',
        '/ping' => 'ping',
        default => 'other',
    };

    if ($route === 'other') {
        $response->status(404);
        $response->end(json_encode(['error' => 'not_found', 'path' => $path], JSON_THROW_ON_ERROR));

        return;
    }

    try {
        $started = hrtime(true);
        $effectiveBusy = $route === 'ping' ? 0 : $busyMs;
        $effectiveSleep = $route === 'ping' ? 0 : $sleepMs;
        $effectiveDepth = $route === 'ping' ? 0 : $stackDepth;

        if ($effectiveDepth > 0) {
            deepStackWork($effectiveDepth, $effectiveBusy);
        } else {
            busyWork($effectiveBusy);
        }
        if ($effectiveSleep > 0) {
            usleep($effectiveSleep * 1000);
        }
        $elapsedMs = (hrtime(true) - $started) / 1_000_000;

        $response->end(json_encode([
            'ok' => true,
            'route' => $route,
            'method' => $method,
            'busy_ms' => $effectiveBusy,
            'sleep_ms' => $effectiveSleep,
            'stack_depth' => $effectiveDepth,
            'elapsed_ms' => round($elapsedMs, 3),
            'profiling_enabled' => $profilingEnabled,
            'profiler' => 'continuous',
            'spool_dir' => $spoolDir,
            'runtime' => 'swoole',
        ], JSON_THROW_ON_ERROR));
    } catch (Throwable $e) {
        $response->status(500);
        $response->end(json_encode([
            'error' => 'worker_exception',
            'message' => $e->getMessage(),
        ], JSON_THROW_ON_ERROR));
    }
});

$server->start();
