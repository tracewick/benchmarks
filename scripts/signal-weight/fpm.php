<?php
require __DIR__ . '/capture.php';
header('Content-Type: application/json');
echo json_encode(capture('fpm', $_GET['run']), JSON_THROW_ON_ERROR);
