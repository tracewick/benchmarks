# Report: rps-pipeline — 2026-11-06

Methodology: [METHOD.md](../../METHOD.md) (high-RPS pipeline / spool). Limitations: [LIMITATIONS.md](../../LIMITATIONS.md).

Raw artifacts: `rps-pipeline-20261106T235239Z/`.

## Scope

- PHP-FPM + `UnitOfWorkProfiler` + `SpoolSink` + reader=`agent`.
- Path `/work` with `WORK_STACK_DEPTH=48` (deeper stacks → larger spool payloads; wall budget still `WORK_BUSY_MS`).
- **Single instance:** sustained RPS is the ceiling of this host + work unit + FPM pool (often co-located k6), not a universal Tracewick SLO or multi-node fleet result.
- Not ContinuousProfiler / RoadRunner / Swoole.

## Identity

| Field | Value |
| --- | --- |
| Date (UTC) | 2026-11-06T23:57:45Z |
| This repo SHA | `e9c36a0fc007d73d5c5e392db328869350df5190` |
| Host | Linux nsk-1-vm-tsr3 7.0.0-42-generic #42-Ubuntu SMP PREEMPT_DYNAMIC Thu Oct 15 08:06:44 UTC 2026 x86_64 GNU/Linux |
| Make target | `make bench-rps` |

## Pins

| Component | Value |
| --- | --- |
| RATE (target) | 700 req/s |
| DURATION | 5m |
| sampleRate | 0.1 |
| WORK_STACK_DEPTH | 48 |
| PHP_FPM_MAX_CHILDREN | 32 |
| READER | agent |
| PATH | /work |

## k6

| Metric | Value |
| --- | --- |
| Achieved RPS | 697.5831709474521 |
| http_req_failed | 0.000% |
| Latency med | 41.38 ms |
| Latency p95 | 51.04 ms |
| Latency p99 | 58.59 ms |

## Spool pipeline

| Metric | Value |
| --- | --- |
| Samples | 124 |
| Files max / last | 222 / 109 |
| Bytes max / last | 0.57 MiB / 0.23 MiB |

## What we proved / did not measure

- Pipeline under this arrival rate: HTTP fail-open, spool files/bytes trajectory, drain on/off as configured.
- Did **not** claim a universal 3k RPS SLO; ceiling depends on host and stack depth.
