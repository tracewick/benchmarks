<?php
declare(strict_types=1);

mt_srand(20261123);
foreach ([48,256] as $depth) {
    foreach ([100,1000] as $hz) {
        foreach ([1,128] as $cycles) {
            for ($round = 1; $round <= 7; ++$round) {
                $modes = ['off','batched','immediate','otel','deferred','history'];
                shuffle($modes);
                foreach ($modes as $position => $mode) {
                    $proc = proc_open([PHP_BINARY,'-d','pcov.enabled=0','-d','opcache.enable_cli=0',
                        __DIR__.'/worker.php',$mode,$hz,$depth,$cycles], [1 => ['pipe','w']], $pipes);
                    $row = json_decode(stream_get_contents($pipes[1]), true, flags: JSON_THROW_ON_ERROR);
                    fclose($pipes[1]);
                    if (proc_close($proc) || $row['checksum'] !== ($expected ??= $row['checksum'])) {
                        throw new RuntimeException('Worker failure or checksum mismatch');
                    }
                    echo json_encode($row + compact('round','position')), "\n";
                }
            }
        }
    }
}
