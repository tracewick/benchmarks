<?php

declare(strict_types=1);

/**
 * RoadRunner HTTP worker — same synthetic /work as public/index.php (FPM).
 *
 * UnitOfWorkProfiler + SpoolSink are constructed **once per worker process**. Creating a new
 * Excimer-backed profiler on every request in a long-lived RR worker caused linear RSS growth
 * (~+1 GiB / 6h @ 10 RPS). FPM recycles processes, so per-request create there is fine.
 */

use Nyholm\Psr7\Factory\Psr17Factory;
use Nyholm\Psr7\Response;
use Spiral\RoadRunner\Http\PSR7Worker;
use Spiral\RoadRunner\Worker;
use Tracewick\Profile\Labels;
use Tracewick\Runtime\ProfilerConfig;
use Tracewick\Runtime\UnitOfWorkProfiler;
use Tracewick\Sink\SpoolSink;
use Tracewick\Transport\SpoolConfig;

require __DIR__ . '/vendor/autoload.php';
require __DIR__ . '/src/SyntheticWork.php';

$psr17 = new Psr17Factory();
$rr = new PSR7Worker(Worker::create(), $psr17, $psr17, $psr17);

$enabledRaw = getenv('TRACEWICK_ENABLED');
$profilingEnabled = $enabledRaw === false || $enabledRaw === ''
    ? true
    : !in_array(strtolower((string) $enabledRaw), ['0', 'false', 'off', 'no'], true);

$spoolDir = getenv('TRACEWICK_SPOOL_DIR') ?: '/var/spool/tracewick';
$sampleRate = (float) (getenv('TRACEWICK_SAMPLE_RATE') ?: '0.1');
$spoolMaxFiles = max(1, (int) (getenv('TRACEWICK_SPOOL_MAX_FILES') ?: '500'));
$service = getenv('TRACEWICK_SERVICE') ?: 'benchmarks-workload';
$envLabel = getenv('TRACEWICK_ENV') ?: 'bench';
$busyMs = max(0, (int) (getenv('WORK_BUSY_MS') ?: '25'));
$sleepMs = max(0, (int) (getenv('WORK_SLEEP_MS') ?: '10'));
$stackDepth = max(0, (int) (getenv('WORK_STACK_DEPTH') ?: '0'));

$profiler = null;
if ($profilingEnabled) {
    $profiler = UnitOfWorkProfiler::create(
        new SpoolSink($service, new SpoolConfig($spoolDir, maxFiles: $spoolMaxFiles)),
        new ProfilerConfig(
            new Labels([
                'service' => $service,
                'env' => $envLabel,
                'runtime' => 'roadrunner',
            ]),
            sampleRate: $sampleRate,
        ),
    );
    // Flush anything still buffered if the worker exits mid-request.
    $profiler->registerShutdown();
}

while ($request = $rr->waitRequest()) {
    try {
        $path = $request->getUri()->getPath() ?: '/';
        $method = $request->getMethod();

        if ($path === '/health') {
            $body = json_encode([
                'ok' => true,
                'excimer' => extension_loaded('excimer'),
                'tracewick' => class_exists(UnitOfWorkProfiler::class),
                'profiling_enabled' => $profilingEnabled,
                'sample_rate' => $sampleRate,
                'spool_max_files' => $spoolMaxFiles,
                'work_stack_depth' => $stackDepth,
                'runtime' => 'roadrunner',
                'rr_num_workers' => max(1, (int) (getenv('RR_NUM_WORKERS') ?: '4')),
            ], JSON_THROW_ON_ERROR);
            $rr->respond(new Response(200, ['Content-Type' => 'application/json'], $body));

            continue;
        }

        $route = match ($path) {
            '/', '/work' => 'work',
            '/ping' => 'ping',
            default => 'other',
        };

        if ($route === 'other') {
            $body = json_encode(['error' => 'not_found', 'path' => $path], JSON_THROW_ON_ERROR);
            $rr->respond(new Response(404, ['Content-Type' => 'application/json'], $body));

            continue;
        }

        if ($profiler !== null) {
            $profiler->start(['route' => $route, 'method' => $method]);
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

            $body = json_encode([
                'ok' => true,
                'route' => $route,
                'busy_ms' => $effectiveBusy,
                'sleep_ms' => $effectiveSleep,
                'stack_depth' => $effectiveDepth,
                'elapsed_ms' => round($elapsedMs, 3),
                'profiling_enabled' => $profilingEnabled,
                'sample_rate' => $sampleRate,
                'spool_dir' => $spoolDir,
                'runtime' => 'roadrunner',
            ], JSON_THROW_ON_ERROR);
            $rr->respond(new Response(200, ['Content-Type' => 'application/json'], $body));
        } finally {
            if ($profiler !== null) {
                $profiler->stop();
                $profiler->flush();
            }
        }
    } catch (Throwable $e) {
        $rr->respond(new Response(
            500,
            ['Content-Type' => 'application/json'],
            json_encode(['error' => 'worker_exception', 'message' => $e->getMessage()], JSON_THROW_ON_ERROR),
        ));
    }
}
