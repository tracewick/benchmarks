<?php
require '/workspace/signal-verification/vendor/autoload.php';
require __DIR__ . '/capture.php';
$factory = new Nyholm\Psr7\Factory\Psr17Factory();
$worker = new Spiral\RoadRunner\Http\PSR7Worker(Spiral\RoadRunner\Worker::create(), $factory, $factory, $factory);
while ($request = $worker->waitRequest()) {
    parse_str($request->getUri()->getQuery(), $query);
    $worker->respond(new Nyholm\Psr7\Response(200, ['Content-Type' => 'application/json'], json_encode(capture('rr', $query['run']), JSON_THROW_ON_ERROR)));
}
