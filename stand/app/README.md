# Workload application

Minimal PHP-FPM app for capacity smoke / benches. Depends on Packagist `tracewick/tracewick` (pin in `composer.json`, default `0.1.0`).

## Endpoints

| Path | Purpose |
| --- | --- |
| `GET /health` | Liveness JSON (`excimer`, Tracewick class) |
| `GET /` or `/work` | Busy + sleep work unit; profiled via SpoolSink |

## Env

| Variable | Default | Meaning |
| --- | --- | --- |
| `TRACEWICK_SPOOL_DIR` | `/var/spool/tracewick` | Spool directory (shared with drain) |
| `TRACEWICK_ENABLED` | `1` | `0` = baseline (no profiler object); `1` = on |
| `TRACEWICK_SAMPLE_RATE` | `0.1` | Smoke forces `1.0`; M2 on uses `0.1` |
| `TRACEWICK_SERVICE` | `benchmarks-workload` | Pyroscope application / service label |
| `TRACEWICK_ENV` | `bench` | `env` label |
| `WORK_BUSY_MS` / `WORK_SLEEP_MS` | `25` / `10` | Synthetic CPU + wall wait |

RoadRunner (`worker.php`) builds **one** `UnitOfWorkProfiler` per worker process and reuses it
across requests. Per-request `::create()` in long-lived RR workers caused unbounded RSS growth.

Rebuild image when changing `TRACEWICK_VERSION` / Excimer pins (`make build`).
