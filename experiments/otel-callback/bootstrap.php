<?php

declare(strict_types=1);

$source = getenv('TRACEWICK_SOURCE') ?: dirname(__DIR__, 3) . '/tracewick';
require $source . '/vendor/autoload.php';
require __DIR__ . '/vendor/autoload.php';

function experimentContext(): ?array
{
    $context = OpenTelemetry\API\Trace\Span::getCurrent()->getContext();

    return $context->isValid() && !$context->isRemote()
        ? [$context->getTraceId(), $context->getSpanId()]
        : null;
}

function experimentProvider(?OpenTelemetry\SDK\Trace\SamplerInterface $sampler = null, array $processors = []): OpenTelemetry\SDK\Trace\TracerProvider
{
    return new OpenTelemetry\SDK\Trace\TracerProvider(
        spanProcessors: $processors,
        sampler: $sampler ?? new OpenTelemetry\SDK\Trace\Sampler\AlwaysOnSampler(),
        resource: OpenTelemetry\SDK\Resource\ResourceInfo::create(
            OpenTelemetry\SDK\Common\Attribute\Attributes::create(['service.name' => 'otel-callback-experiment']),
        ),
    );
}
