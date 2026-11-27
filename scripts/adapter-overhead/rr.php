<?php

declare(strict_types=1);

use Nyholm\Psr7\Factory\Psr17Factory;
use Spiral\RoadRunner\Http\PSR7Worker;
use Spiral\RoadRunner\Worker;
use Tracewick\Bridge\Psr15\TracewickMiddleware;
use Tracewick\Runtime\ProfilerConfig;
use Tracewick\Runtime\UnitOfWorkProfiler;
use Tracewick\Sink\SpoolSink;
use Tracewick\Transport\SpoolConfig;

require '/workspace/psr-15/examples/roadrunner/vendor/autoload.php';
require __DIR__ . '/handler.php';

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
$factory = new Psr17Factory();
$server = new PSR7Worker(Worker::create(), $factory, $factory, $factory);

while (($request = $server->waitRequest()) !== null) {
    try {
        $server->respond($middleware !== null && $request->getUri()->getPath() === '/work'
            ? $middleware->process($request, $handler)
            : $handler->handle($request));
    } finally {
        $profiler?->flush();
    }
}
