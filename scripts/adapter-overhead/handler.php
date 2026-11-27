<?php

declare(strict_types=1);

use Nyholm\Psr7\Response;
use Psr\Http\Message\ResponseInterface;
use Psr\Http\Message\ServerRequestInterface;
use Psr\Http\Server\RequestHandlerInterface;

require __DIR__ . '/../runtime-preflight/fixed-work.php';

$operations = (int) getenv('TW_OPERATIONS');
$handler = new class ($operations) implements RequestHandlerInterface {
    public function __construct(private readonly int $operations) {}

    public function handle(ServerRequestInterface $request): ResponseInterface
    {
        if ($request->getUri()->getPath() === '/__ready') {
            return new Response(204);
        }
        if ($request->getUri()->getPath() === '/__worker') {
            $stat = file_get_contents('/proc/self/stat');
            $fields = explode(' ', substr($stat, strrpos($stat, ') ') + 2));
            $status = file_get_contents('/proc/self/status');
            preg_match('/^VmRSS:\s+(\d+) kB$/m', $status, $rss);
            preg_match('/^VmHWM:\s+(\d+) kB$/m', $status, $highWater);
            return new Response(200, ['Content-Type' => 'application/json'], json_encode([
                'pid' => getmypid(),
                'start_ticks' => (int) $fields[19],
                'cpu_ticks' => (int) $fields[11] + (int) $fields[12],
                'rss_kib' => (int) $rss[1],
                'high_water_kib' => (int) $highWater[1],
            ], JSON_THROW_ON_ERROR));
        }
        if ($request->getUri()->getPath() !== '/work') {
            return new Response(404);
        }

        return new Response(
            200,
            ['Content-Type' => 'text/plain', 'X-Worker-Pid' => (string) getmypid()],
            $this->operations . ':' . fixedStackWork(24, $this->operations),
        );
    }
};
