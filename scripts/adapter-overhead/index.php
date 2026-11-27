<?php

declare(strict_types=1);

use Nyholm\Psr7\Factory\Psr17Factory;
use Nyholm\Psr7Server\ServerRequestCreator;
use Tracewick\Bridge\Psr15\TracewickMiddleware;
use Tracewick\Runtime\ProfilerConfig;
use Tracewick\Runtime\UnitOfWorkProfiler;
use Tracewick\Sink\SpoolSink;
use Tracewick\Transport\SpoolConfig;

require '/workspace/psr-15/examples/frankenphp/vendor/autoload.php';
require __DIR__ . '/handler.php';

$factory = new Psr17Factory();
$requests = new ServerRequestCreator($factory, $factory, $factory, $factory);
$middleware = null;
$profiler = null;

if (getenv('TW_ENABLED') === '1') {
    $profiler = UnitOfWorkProfiler::create(
        new SpoolSink('tracewick-psr15-overhead', new SpoolConfig('/dev/shm/spool')),
        new ProfilerConfig(),
    );
    $profiler->registerShutdown();
    $middleware = new TracewickMiddleware($profiler, routeResolver: static fn(): string => 'work', flushAfterHandler: false);
}

$handle = static function () use ($requests, $handler, $middleware): void {
    $request = $requests->fromGlobals();
    $result = $middleware !== null && $request->getUri()->getPath() === '/work'
        ? $middleware->process($request, $handler)
        : $handler->handle($request);
    http_response_code($result->getStatusCode());
    foreach ($result->getHeaders() as $name => $values) {
        foreach ($values as $value) {
            header($name . ': ' . $value, false);
        }
    }
    echo $result->getBody();
    frankenphp_finish_request();
};
do {
    try {
        $keepRunning = frankenphp_handle_request($handle);
    } finally {
        $profiler?->flush();
    }
} while ($keepRunning);
