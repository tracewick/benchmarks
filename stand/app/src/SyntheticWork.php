<?php

declare(strict_types=1);

/**
 * Shared synthetic CPU work for FPM and RoadRunner workers.
 * Wall budget stays in busyWork; WORK_STACK_DEPTH only deepens frames.
 */

/**
 * Burn roughly $milliseconds of CPU so wall/cpu samples have something to catch.
 * Unchanged leaf used by all scenarios when WORK_STACK_DEPTH=0.
 */
function busyWork(int $milliseconds): void
{
    if ($milliseconds <= 0) {
        return;
    }

    $deadline = hrtime(true) + ($milliseconds * 1_000_000);
    $x = 0.0;
    while (hrtime(true) < $deadline) {
        $x += sin($x + 1.2345);
        if ($x > 1_000_000.0) {
            $x = 0.0;
        }
    }
}

/**
 * Opt-in deeper call stacks for high-RPS / spool-size honesty.
 * Wall budget stays in busyWork at the leaf — same WORK_BUSY_MS as shallow mode.
 */
function deepStackWork(int $depth, int $milliseconds): void
{
    stackLayerA($depth, $milliseconds);
}

function stackLayerA(int $depth, int $milliseconds): void
{
    if ($depth <= 1) {
        busyWork($milliseconds);

        return;
    }
    stackLayerB($depth - 1, $milliseconds);
}

function stackLayerB(int $depth, int $milliseconds): void
{
    if ($depth <= 1) {
        busyWork($milliseconds);

        return;
    }
    stackLayerC($depth - 1, $milliseconds);
}

function stackLayerC(int $depth, int $milliseconds): void
{
    if ($depth <= 1) {
        busyWork($milliseconds);

        return;
    }
    stackLayerD($depth - 1, $milliseconds);
}

function stackLayerD(int $depth, int $milliseconds): void
{
    if ($depth <= 1) {
        busyWork($milliseconds);

        return;
    }
    stackLayerE($depth - 1, $milliseconds);
}

function stackLayerE(int $depth, int $milliseconds): void
{
    if ($depth <= 1) {
        busyWork($milliseconds);

        return;
    }
    stackLayerF($depth - 1, $milliseconds);
}

function stackLayerF(int $depth, int $milliseconds): void
{
    if ($depth <= 1) {
        busyWork($milliseconds);

        return;
    }
    stackLayerG($depth - 1, $milliseconds);
}

function stackLayerG(int $depth, int $milliseconds): void
{
    if ($depth <= 1) {
        busyWork($milliseconds);

        return;
    }
    stackLayerH($depth - 1, $milliseconds);
}

function stackLayerH(int $depth, int $milliseconds): void
{
    if ($depth <= 1) {
        busyWork($milliseconds);

        return;
    }
    stackLayerA($depth - 1, $milliseconds);
}
