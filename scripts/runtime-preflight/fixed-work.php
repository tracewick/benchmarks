<?php

declare(strict_types=1);

/**
 * A fixed number of deterministic integer operations, independent of wall time.
 * The checksum depends on the operation count through a full-period LCG.
 */
function fixedWork(int $iterations): int
{
    $value = 1;
    for ($i = 0; $i < $iterations; ++$i) {
        $value = ($value * 1664525 + 1013904223) & 2147483647;
    }

    return $value;
}

function fixedStackWork(int $depth, int $iterations): int
{
    return fixedLayerA($depth, $iterations);
}

function fixedLayerA(int $depth, int $iterations): int
{
    return $depth <= 1 ? fixedWork($iterations) : fixedLayerB($depth - 1, $iterations);
}

function fixedLayerB(int $depth, int $iterations): int
{
    return $depth <= 1 ? fixedWork($iterations) : fixedLayerC($depth - 1, $iterations);
}

function fixedLayerC(int $depth, int $iterations): int
{
    return $depth <= 1 ? fixedWork($iterations) : fixedLayerD($depth - 1, $iterations);
}

function fixedLayerD(int $depth, int $iterations): int
{
    return $depth <= 1 ? fixedWork($iterations) : fixedLayerE($depth - 1, $iterations);
}

function fixedLayerE(int $depth, int $iterations): int
{
    return $depth <= 1 ? fixedWork($iterations) : fixedLayerF($depth - 1, $iterations);
}

function fixedLayerF(int $depth, int $iterations): int
{
    return $depth <= 1 ? fixedWork($iterations) : fixedLayerG($depth - 1, $iterations);
}

function fixedLayerG(int $depth, int $iterations): int
{
    return $depth <= 1 ? fixedWork($iterations) : fixedLayerH($depth - 1, $iterations);
}

function fixedLayerH(int $depth, int $iterations): int
{
    return $depth <= 1 ? fixedWork($iterations) : fixedLayerA($depth - 1, $iterations);
}
