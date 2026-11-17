<?php
require '/workspace/tracewick/vendor/autoload.php';
foreach (glob($argv[1] . '/*/*.spool') as $path) {
    $file = Tracewick\Sink\SpoolFile::fromBytes(file_get_contents($path));
    $parts = (new Tracewick\Encoder\CompactStacksCodec())->decode($file->payload);
    $events = array_sum(array_map(static fn($s): int => $s->count, $parts->stacks));
    $profile = new Tracewick\Profile\Profile($file->eventType, $file->periodNs, $file->startNs, $file->endNs, $parts->frames, $parts->stacks);
    $bytes = (new Tracewick\Encoder\PprofEncoder())->encode($profile);
    file_put_contents($path . '.php.pprof', $bytes);
    echo json_encode(['file' => basename($path), 'events' => $events, 'period_ns' => $file->periodNs, 'application' => $file->application]), "\n";
}
