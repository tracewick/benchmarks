<?php

declare(strict_types=1);

// Exercise original package metadata separately from the root runtime test project.
$directory = '/evidence/install-probe';
mkdir($directory, 0755, true);
file_put_contents($directory . '/composer.json', json_encode([
    'name' => 'tracewick-bench/source-install-probe',
    'require' => [
        'php' => '^8.4',
        'symfony/framework-bundle' => '7.4.*',
        'tracewick/symfony-bundle' => 'dev-develop',
        'tracewick/tracewick' => '1.0.0-dev',
    ],
    'repositories' => [
        ['type' => 'path', 'url' => '/sources/bundle', 'options' => [
            'symlink' => false, 'versions' => ['tracewick/symfony-bundle' => 'dev-develop'],
        ]],
        ['type' => 'path', 'url' => '/srv/app/vendor/tracewick/tracewick', 'options' => [
            'symlink' => false, 'versions' => ['tracewick/tracewick' => '1.0.0-dev'],
        ]],
    ],
    'minimum-stability' => 'stable', 'prefer-stable' => true,
], JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR));
chdir($directory);
passthru('composer update --dry-run --no-plugins --no-scripts --no-interaction --no-progress 2>&1', $code);
file_put_contents($directory . '/result.json', json_encode([
    'status' => 0 === $code ? 'passed' : 'failed', 'composer_exit_code' => $code,
    'core_source_version_for_resolution' => '1.0.0-dev',
    'note' => 'Source dependency-resolution probe. No RC or tag is created.',
], JSON_PRETTY_PRINT | JSON_THROW_ON_ERROR));
exit($code);
