# OTel callback feasibility experiment

This is an opt-in development experiment, not an application integration. It reads the current
OpenTelemetry context in a native Excimer callback and forwards that log exactly once to the real
Tracewick sampler. It does not implement correlated stacks, schema 2 or metadata delivery.

See [METHOD.md](../../METHOD.md). A fixed-work CLI loop is used instead of k6 because this probe
isolates in-process callback cost and final log processing; no HTTP or server capacity is measured.
The [report](../../reports/2026-11-17-otel-callback-preflight.md) records versions and limitations.

Requirements: Linux, PHP 8.5 with Excimer 1.2.7, Composer, and coreutils `timeout`. Use a local core
checkout with its Composer dependencies installed. OTel dependencies are isolated here; they are
not required by Tracewick. The committed lock pins this experiment's dependency graph.

```bash
composer install --working-dir=experiments/otel-callback
export TRACEWICK_SOURCE=/absolute/path/to/tracewick
mkdir -p reports/_local/otel-callback
php -d pcov.enabled=0 -d opcache.enable_cli=0 experiments/otel-callback/sdk.php
php -d pcov.enabled=0 -d opcache.enable_cli=0 experiments/otel-callback/sdk.php --rotation
php -d pcov.enabled=0 -d opcache.enable_cli=0 experiments/otel-callback/run.php \
  reports/_local/otel-callback/overhead.json 7 500
```

The runner uses 7 rounds and targets approximately 500 ms of unprofiled work per row by default.
It calibrates a fixed iteration count, then shuffles four modes within every round using seed
20261117. All rows run in separate PHP processes with the same recording SDK span active:

- `off`: no sampler.
- `batched`: the real sampler with a 10,000-entry native threshold.
- `immediate`: one-entry threshold, with an observer wrapper but no OTel reads.
- `otel`: the same wrapper plus a valid-local-context read and trace/span pair construction.

Modes run at 100/1000 Hz and configured depths 48/256. The recursive workload reaches those
depth caps. Coverage and CLI opcache are disabled. `work_wall_ns` times only the equal work;
`total_wall_ns` and `total_cpu_ns` also include start/stop and final flush, so the batched mode's
deferred aggregation is counted. SDK setup and span export are outside these intervals. Each
worker has a 15-second outer timeout. The runner checks workload checksum and sampler failures;
a partial output file after failure is not a completed result.

`sdk.php` separately exercises real recording and nonrecording SDK spans, nested scopes,
restoration, an ended-but-still-active span, remote-parent omission and a local child. It checks
frame-marked observations, weight conservation, callback autoload/warnings and exporter entry.
The `--rotation` mode also exercises real automatic UoW rotation and deferred sink delivery.
Core classes are not manually preloaded by the probe. `experimentContext()` is called once at
bootstrap to initialize the optional reader path before collection.

For a targeted syscall check, install `strace` in the test environment and run:

```bash
OTEL_PROBE_MARKERS=1 strace -f -qq -s 512 -e trace=%file,%network,read,write,close \
  -o reports/_local/otel-callback/sdk.strace \
  php -d pcov.enabled=0 experiments/otel-callback/sdk.php \
  3>reports/_local/otel-callback/sdk-markers.log
python3 experiments/otel-callback/trace.py reports/_local/otel-callback/sdk.strace
```

Marker writes are intentional instrumentation and excluded. This checks the selected syscall set,
not every possible side effect. Do not use strace or these markers for overhead measurements.
Keep raw traces local: they include source and environment paths.

These short runs are not a memory soak, supported-PHP matrix, production overhead guarantee or
validation of custom OTel storage. The future correlation-aware builder adds work not present
here and must be measured when implemented. Do not run this experiment on an occupied soak VPS.
