<?php

declare(strict_types=1);

function nativeWork(bool $profile, bool $trace = false): array
{
    $events = 0;
    $p = null;
    if ($profile) {
        $p = new ExcimerProfiler();
        $p->setEventType(EXCIMER_REAL);
        $p->setPeriod(0.001);
        $p->setFlushCallback(static function (ExcimerLog $log) use (&$events, $trace): void {
            $events += $log->getEventCount();
            if ($trace) {
                foreach ($log as $entry) {
                    $entry->getTrace();
                }
            }
        }, 16);
        $p->start();
    }
    $until = hrtime(true) + 200_000_000;
    while (hrtime(true) < $until) {}
    if ($p !== null) {
        $p->stop();
        $p->flush();
    }
    return ['events' => $events];
}
