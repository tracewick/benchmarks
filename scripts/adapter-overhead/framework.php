<?php

declare(strict_types=1);

use Illuminate\Contracts\Http\Kernel as LaravelKernel;
use Illuminate\Foundation\Application;
use Illuminate\Http\Request as LaravelRequest;
use Illuminate\Routing\Router;
use Nyholm\Psr7\Factory\Psr17Factory;
use Nyholm\Psr7\Response as PsrResponse;
use Spiral\RoadRunner\Http\PSR7Worker;
use Spiral\RoadRunner\Worker;
use Symfony\Bundle\FrameworkBundle\FrameworkBundle;
use Symfony\Bundle\FrameworkBundle\Kernel\MicroKernelTrait;
use Symfony\Component\DependencyInjection\Loader\Configurator\ContainerConfigurator;
use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\HttpFoundation\Response;
use Symfony\Component\HttpKernel\Kernel;
use Symfony\Component\Routing\Loader\Configurator\RoutingConfigurator;
use Tracewick\Bridge\Laravel\TracewickServiceProvider;
use Tracewick\Bridge\Symfony\TracewickBundle;

$source = '/framework-inputs';
$workspace = '/workspace';
$runtime = getenv('TW_FRAMEWORK');

require $workspace . '/psr-15/examples/roadrunner/vendor/autoload.php';
require __DIR__ . '/handler.php';

function workResponse(): Response
{
    $operations = (int) getenv('TW_OPERATIONS');

    return new Response(
        $operations . ':' . fixedStackWork(24, $operations),
        200,
        ['Content-Type' => 'text/plain', 'X-Worker-Pid' => (string) getmypid()],
    );
}

if ($runtime === 'symfony') {
    $loader = require __DIR__ . '/symfony/vendor/autoload.php';
    $loader->setPsr4('Tracewick\\Bridge\\Symfony\\', $source . '/symfony/src');

    $kernel = new class ('prod', false) extends Kernel {
        use MicroKernelTrait;

        public function registerBundles(): iterable
        {
            yield new FrameworkBundle();
            yield new TracewickBundle();
        }

        public function getProjectDir(): string
        {
            return __DIR__;
        }

        public function getCacheDir(): string
        {
            return '/tmp/benchmark-symfony/cache';
        }

        private function configureContainer(ContainerConfigurator $container): void
        {
            $container->extension('framework', ['http_method_override' => false]);
            $container->extension('tracewick', [
                'enabled' => getenv('TW_ENABLED') === '1',
                'application_name' => 'tracewick-symfony-overhead',
                'sample_rate' => 0.1,
                'spool_directory' => '/dev/shm/spool',
            ]);
        }

        private function configureRoutes(RoutingConfigurator $routes): void
        {
            $routes->add('work', '/work')->controller('kernel::work');
        }

        public function work(): Response
        {
            return workResponse();
        }
    };
    $kernel->boot();
    $createRequest = static fn(): Request => Request::create('/work');
} elseif ($runtime === 'laravel') {
    $loader = require __DIR__ . '/laravel/vendor/autoload.php';
    $loader->setPsr4('Tracewick\\Bridge\\Laravel\\', $source . '/laravel/src');

    $appPath = '/tmp/benchmark-laravel';
    mkdir($appPath . '/bootstrap/cache', 0700, true);
    mkdir($appPath . '/config', 0700, true);
    // Package discovery stays empty in the minimal app. Register the actual provider explicitly.
    $app = Application::configure(basePath: $appPath)
        ->withRouting(using: static function (): void {
            app(Router::class)->get('/work', workResponse(...))->name('work');
        })
        ->withProviders([TracewickServiceProvider::class], withBootstrapProviders: false)
        ->withExceptions()
        ->create();
    $kernel = $app->make(LaravelKernel::class);
    $kernel->bootstrap();
    $createRequest = static fn(): LaravelRequest => LaravelRequest::create('/work');
} else {
    throw new RuntimeException('Select a supported framework with TW_FRAMEWORK.');
}

$factory = new Psr17Factory();
$server = new PSR7Worker(Worker::create(), $factory, $factory, $factory);
while (($request = $server->waitRequest()) !== null) {
    if ($request->getUri()->getPath() !== '/work') {
        $server->respond($handler->handle($request));
        continue;
    }

    $frameworkRequest = $createRequest();
    $response = $kernel->handle($frameworkRequest);
    try {
        $server->respond(new PsrResponse(
            $response->getStatusCode(),
            $response->headers->all(),
            (string) $response->getContent(),
        ));
    } finally {
        $kernel->terminate($frameworkRequest, $response);
    }
}
