<?php
require __DIR__ . '/capture.php';
for ($i = 0; $i < 10; ++$i) {
    echo json_encode(capture('cli', $argv[1]), JSON_THROW_ON_ERROR), "\n";
}
