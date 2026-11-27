<?php

declare(strict_types=1);

use Nyholm\Psr7\ServerRequest;
use Swoole\Http\Request;
use Swoole\Http\Response;
use Swoole\Http\Server;
use Tracewick\Profile\Labels;
use Tracewick\Runtime\ContinuousProfiler;
use Tracewick\Runtime\ContinuousProfilerConfig;
use Tracewick\Runtime\SpoolAggregationWindow;
use Tracewick\Sink\SpoolSink;
use Tracewick\Transport\SpoolConfig;

require '/workspace/psr-15/examples/swoole/vendor/autoload.php';
require __DIR__ . '/handler.php';

$server = new Server('127.0.0.1', 18150);
$server->set(['worker_num' => 1, 'enable_coroutine' => true, 'max_wait_time' => 5]);
$profiler = null;
$lastPulseSecond = null;

$server->on('WorkerStart', static function () use (&$profiler): void {
    if (getenv('TW_ENABLED') === '1') {
        $application = 'tracewick-psr15-overhead';
        $profiler = ContinuousProfiler::create(
            new SpoolSink($application, new SpoolConfig('/dev/shm/spool')),
            new ContinuousProfilerConfig($application, new Labels(['runtime' => 'swoole']), new SpoolAggregationWindow()),
        );
        $profiler->start();
        $profiler->registerShutdown();
    }
});
$server->on('Request', static function (Request $request, Response $response) use ($handler, &$profiler, &$lastPulseSecond): void {
    $path = $request->server['request_uri'] ?? '/';
    try {
        $result = $handler->handle(new ServerRequest('GET', $path));
        $response->status($result->getStatusCode());
        foreach ($result->getHeaders() as $name => $values) {
            $response->header($name, $values);
        }
        $response->end((string) $result->getBody());
    } finally {
        if ($profiler !== null && $path === '/work') {
            $second = intdiv(hrtime(true), 1_000_000_000);
            if ($second !== $lastPulseSecond) {
                $lastPulseSecond = $second;
                $profiler->pulse();
            }
        }
    }
});
$server->on('WorkerStop', static function () use (&$profiler): void {
    $profiler?->stop();
});
$server->start();
