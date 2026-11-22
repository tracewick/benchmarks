<?php

declare(strict_types=1);

namespace TracewickBench\Preflight;

use Psr\Log\NullLogger;
use Symfony\Bundle\FrameworkBundle\Console\Application;
use Symfony\Bundle\FrameworkBundle\FrameworkBundle;
use Symfony\Bundle\FrameworkBundle\Kernel\MicroKernelTrait;
use Symfony\Component\Console\Command\Command;
use Symfony\Component\Console\Input\ArrayInput;
use Symfony\Component\Console\Input\InputInterface;
use Symfony\Component\Console\Input\InputOption;
use Symfony\Component\Console\Output\BufferedOutput;
use Symfony\Component\Console\Output\OutputInterface;
use Symfony\Component\DependencyInjection\Loader\Configurator\ContainerConfigurator;
use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\HttpFoundation\Response;
use Symfony\Component\HttpKernel\HttpKernelInterface;
use Symfony\Component\HttpKernel\Kernel;
use Symfony\Component\Messenger\MessageBusInterface;
use Symfony\Component\Routing\Loader\Configurator\RoutingConfigurator;
use Tracewick\Bridge\Symfony\Profiler\HttpProfiler;
use Tracewick\Bridge\Symfony\Profiler\UnitOfWorkHttpProfiler;
use Tracewick\Bridge\Symfony\TracewickBundle;
use Tracewick\Sink\SpoolFile;

require '/srv/bundle/vendor/autoload.php';

function verify(bool $condition, string $message): void
{
    if (!$condition) {
        throw new \RuntimeException($message);
    }
}

function busyWork(): void
{
    $until = hrtime(true) + 25_000_000;
    while (hrtime(true) < $until) {
        hash('sha256', (string) hrtime(true));
    }
}

final readonly class WorkMessage
{
    public function __construct(public bool $fail = false, public int $sleepUs = 0) {}
}

final class WorkHandler
{
    public static int $handled = 0;
    public static int $failed = 0;

    public function __invoke(WorkMessage $message): void
    {
        busyWork();
        if ($message->sleepUs > 0) {
            usleep($message->sleepUs);
        }
        if ($message->fail) {
            ++self::$failed;
            throw new \RuntimeException('Intentional Messenger handler failure');
        }
        ++self::$handled;
    }
}

final class WorkCommand extends Command
{
    public function __construct()
    {
        parent::__construct('preflight:work');
    }

    protected function configure(): void
    {
        $this->addOption('fail', null, InputOption::VALUE_NONE);
    }

    protected function execute(InputInterface $input, OutputInterface $output): int
    {
        busyWork();
        if ($input->getOption('fail')) {
            throw new \RuntimeException('Intentional console failure');
        }

        return Command::SUCCESS;
    }
}

final class PreflightKernel extends Kernel
{
    use MicroKernelTrait;

    public function __construct(private readonly string $workdir, private readonly float $sampleRate)
    {
        parent::__construct('preflight', false);
    }

    public function getProjectDir(): string
    {
        return __DIR__;
    }

    public function getCacheDir(): string
    {
        return $this->workdir . '/cache';
    }

    public function getLogDir(): string
    {
        return $this->workdir . '/logs';
    }

    public function registerBundles(): iterable
    {
        yield new FrameworkBundle();
        yield new TracewickBundle();
    }

    private function configureContainer(ContainerConfigurator $container): void
    {
        $container->extension('framework', [
            'secret' => 'synthetic-preflight', 'test' => true,
            'http_method_override' => false, 'php_errors' => ['log' => false],
            'router' => ['utf8' => true],
            'messenger' => [
                'transports' => ['async' => ['dsn' => 'in-memory://',
                    'retry_strategy' => ['max_retries' => 0]]],
                'routing' => [WorkMessage::class => 'async'],
            ],
        ]);
        $container->extension('tracewick', [
            'application_name' => 'symfony-preflight',
            'sample_rate' => $this->sampleRate,
            'spool_directory' => '/var/spool/tracewick',
            'profile_console' => true, 'profile_messenger' => true,
            'sink' => 'spool', 'base_labels' => ['env' => 'preflight'],
        ]);
        $services = $container->services();
        $services->set('logger', NullLogger::class);
        $services->set(WorkHandler::class)->tag('messenger.message_handler');
        $services->set(WorkCommand::class)->tag('console.command');
    }

    private function configureRoutes(RoutingConfigurator $routes): void
    {
        $routes->add('preflight_work', '/work')->controller('kernel::work');
        $routes->add('preflight_parent', '/parent')->controller('kernel::parentRequest');
        $routes->add('preflight_error', '/error')->controller('kernel::errorRequest');
    }

    public function work(): Response
    {
        busyWork();

        return new Response('ok');
    }

    public function parentRequest(): Response
    {
        return $this->handle(Request::create('/work'), HttpKernelInterface::SUB_REQUEST);
    }

    public function errorRequest(): Response
    {
        busyWork();
        throw new \RuntimeException('Intentional HTTP exception');
    }
}

$mode = $argv[1] ?? 'check';
$seconds = (int) ($argv[2] ?? '1200');
$workdir = '/evidence/' . $mode;
mkdir($workdir, 0755, true);
verify(extension_loaded('excimer'), 'Real Excimer extension is required');
$kernel = new PreflightKernel($workdir, 'check' === $mode ? 1.0 : 0.1);
$kernel->boot();
$container = $kernel->getContainer()->get('test.service_container');
$profiler = $container->get(HttpProfiler::class);
verify($profiler instanceof UnitOfWorkHttpProfiler, 'Bundle returned a no-op profiler');
verify(null === $profiler->diagnostics()->inactiveSampler, 'Sampler is inactive');
$profilerId = spl_object_id($profiler);
$application = new Application($kernel);
$application->setAutoExit(false);
$bus = $container->get('messenger.default_bus');
verify($bus instanceof MessageBusInterface, 'Real Messenger bus is required');
$started = microtime(true);
$http = 0;
$httpErrors = 0;

$handle = static function (string $path) use ($kernel, &$http, &$httpErrors): void {
    $request = Request::create($path);
    $response = $kernel->handle($request);
    verify($response->getStatusCode() === ('/error' === $path ? 500 : 200), 'Unexpected HTTP response');
    $kernel->terminate($request, $response);
    ++$http;
    $httpErrors += (int) ($response->getStatusCode() >= 500);
};

$consume = static function (int $count) use ($application): void {
    $code = $application->run(new ArrayInput([
        'command' => 'messenger:consume', 'receivers' => ['async'],
        '--limit' => $count, '--time-limit' => 1800, '--no-reset' => true,
    ]), new BufferedOutput());
    verify(0 === $code, 'Messenger worker command failed');
};

if ('check' === $mode) {
    for ($i = 0; $i < 30; ++$i) {
        $handle(['/work', '/parent', '/error'][$i % 3]);
    }
    foreach ([false, true] as $fail) {
        $code = $application->run(new ArrayInput([
            'command' => 'preflight:work', '--fail' => $fail,
        ]), new BufferedOutput());
        verify($code === ($fail ? 1 : 0), 'Unexpected console exit code');
    }
    $before = $profiler->diagnostics()->collectedProfiles;
    for ($i = 0; $i < 20; ++$i) {
        $bus->dispatch(new WorkMessage(19 === $i));
    }
    verify($before === $profiler->diagnostics()->collectedProfiles, 'Producer dispatch created a message profile');
    $consume(20);
    verify(19 === WorkHandler::$handled && 1 === WorkHandler::$failed, 'Messenger outcomes differ');
    verify($profiler->diagnostics()->collectedProfiles - $before === 20, 'Worker command overlapped per-message profiles');
    $labels = [];
    foreach (new \RecursiveIteratorIterator(new \RecursiveDirectoryIterator('/var/spool/tracewick', \FilesystemIterator::SKIP_DOTS)) as $file) {
        if (!$file->isFile()) {
            continue;
        }
        $profile = SpoolFile::fromBytes(file_get_contents($file->getPathname()));
        $labels[] = $profile->labels;
        verify(!isset($profile->labels['uri']) && !isset($profile->labels['query']), 'Raw request data became labels');
    }
    verify(52 === count($labels), 'Expected one profile for each of 30 HTTP, 2 CLI and 20 consumed units');
    foreach (['preflight_work', 'preflight_parent', 'preflight_error'] as $route) {
        verify(10 === count(array_filter($labels, static fn(array $label): bool => ($label['route'] ?? null) === $route)), 'Wrong route profile count');
    }
    verify(20 === count(array_filter($labels, static fn(array $label): bool => ($label['message'] ?? null) === WorkMessage::class)), 'Wrong message labels');
    verify(2 === count(array_filter($labels, static fn(array $label): bool => ($label['command'] ?? null) === 'preflight:work')), 'Wrong console labels');
    file_put_contents($workdir . '/labels.json', json_encode($labels, JSON_PRETTY_PRINT | JSON_THROW_ON_ERROR));
} elseif ('http' === $mode) {
    $until = microtime(true) + $seconds;
    while (microtime(true) < $until) {
        $tick = microtime(true);
        $handle(0 === $http % 31 ? '/error' : (0 === $http % 7 ? '/parent' : '/work'));
        usleep((int) max(0, (0.2 - (microtime(true) - $tick)) * 1_000_000));
    }
} elseif ('messenger' === $mode) {
    $count = $seconds * 5;
    for ($i = 0; $i < $count; ++$i) {
        $bus->dispatch(new WorkMessage(0 === $i % 31, 0));
    }
    $consume($count);
    verify($count === WorkHandler::$handled + WorkHandler::$failed, 'Messenger worker ended early');
} else {
    throw new \RuntimeException('Unknown mode');
}
verify($profilerId === spl_object_id($container->get(HttpProfiler::class)), 'Profiler service was replaced');
$memory = static function (): array {
    preg_match('/^VmRSS:\s+(\d+) kB$/m', file_get_contents('/proc/self/status'), $matches);
    return ['php_used_bytes' => memory_get_usage(false), 'php_reserved_bytes' => memory_get_usage(true),
        'rss_bytes' => (int) $matches[1] * 1024];
};
$beforeReset = $memory();
$transport = $container->get('messenger.transport.async');
verify($transport instanceof \Symfony\Component\Messenger\Transport\InMemory\InMemoryTransport, 'Expected in-memory transport');
$transport->reset();
$afterTransportReset = $memory();
$collectedCycles = gc_collect_cycles();
$afterCycleCollection = $memory();
$freedCaches = gc_mem_caches();
$afterReset = $memory();
file_put_contents($workdir . '/memory-reset.json', json_encode([
    'before' => $beforeReset, 'after_transport_reset' => $afterTransportReset,
    'after_cycle_collection' => $afterCycleCollection, 'collected_cycles' => $collectedCycles, 'after' => $afterReset, 'gc_mem_caches_freed_bytes' => $freedCaches,
    'note' => 'Separate 6000-message replay without artificial sleep. Transport reset, cycle collection and allocator-cache release happen after all messages. This is not an overhead comparison.',
], JSON_PRETTY_PRINT | JSON_THROW_ON_ERROR));
$diagnostics = $profiler->diagnostics();
foreach (['droppedProfiles', 'skippedProfiles', 'failedProfiles', 'rejectedProfiles', 'swallowedErrors', 'samplerFailures'] as $key) {
    verify(0 === $diagnostics->$key, 'Unexpected profiler failure: ' . $key);
}
$result = [
    'status' => 'passed', 'mode' => $mode, 'pid' => getmypid(),
    'elapsed_seconds' => microtime(true) - $started,
    'php' => PHP_VERSION, 'excimer' => phpversion('excimer'),
    'http' => $http, 'intentional_http_errors' => $httpErrors,
    'messages_handled' => WorkHandler::$handled, 'intentional_message_failures' => WorkHandler::$failed,
    'profiler_id' => $profilerId, 'diagnostics' => $diagnostics,
    'peak_php_memory_bytes' => memory_get_peak_usage(true),
];
file_put_contents($workdir . '/result.json', json_encode($result, JSON_PRETTY_PRINT | JSON_THROW_ON_ERROR));
echo json_encode($result, JSON_THROW_ON_ERROR), "\n";
$kernel->shutdown();
