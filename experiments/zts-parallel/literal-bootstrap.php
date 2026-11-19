<?php

declare(strict_types=1);

function literalThreadId(): string { return 'unavailable'; }

final class LiteralFixture
{
    public array $items = [];
    public string $tid;

    public function __construct() { $this->tid = literalThreadId(); }
    public function payload(): array { return ['tid' => $this->tid, 'items' => $this->items]; }
}

function literalTask(): array
{
    static $fixture;
    $fixture ??= new LiteralFixture();
    return $fixture->payload();
}
