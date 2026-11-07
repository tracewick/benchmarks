# Report: rps-pipeline — 2026-11-07

Methodology: [METHOD.md](../../METHOD.md) (high-RPS pipeline / spool). Limitations: [LIMITATIONS.md](../../LIMITATIONS.md).

Raw artifacts: `2026-11-07-rps-pipeline-rr-agent-depth48-cloud/`.

## Scope

- RoadRunner + `UnitOfWorkProfiler` + `SpoolSink` + reader=`agent`.
- Path `/work` with `WORK_STACK_DEPTH=48` (deeper stacks → larger spool payloads; wall budget still `WORK_BUSY_MS`).
- **Single instance:** sustained RPS is the ceiling of this host + work unit + worker pool (often co-located k6), not a universal Tracewick SLO or multi-node fleet result.
- Not ContinuousProfiler / Swoole / PHP-FPM.

## Identity

| Field | Value |
| --- | --- |
| Date (UTC) | 2026-11-07T00:21:10Z |
| This repo SHA | `8d658ffbef34d0bb4fcc625299c6e411d6afc263` |
| Host | Linux nsk-1-vm-tsr3 7.0.0-42-generic #42-Ubuntu SMP PREEMPT_DYNAMIC Thu Oct 15 08:06:44 UTC 2026 x86_64 GNU/Linux |
| Make target | `make bench-rps` |

## Pins

| Component | Value |
| --- | --- |
| RATE (target) | 700 req/s |
| DURATION | 5m |
| sampleRate | 0.1 |
| WORK_STACK_DEPTH | 48 |
| RUNTIME | rr |
| RR_NUM_WORKERS | 32 |
| READER | agent |
| PATH | /work |

## k6

| Metric | Value |
| --- | --- |
| Achieved RPS | 697.5530450433149 |
| http_req_failed | 0.000% |
| Latency med | 45.21 ms |
| Latency p95 | 59.98 ms |
| Latency p99 | 75.90 ms |

## Spool pipeline

| Metric | Value |
| --- | --- |
| Samples | 64 |
| Files max / last | 230 / 124 |
| Bytes max / last | 0.48 MiB / 0.26 MiB |

## What we proved / did not measure

- Pipeline under this arrival rate: HTTP fail-open, spool files/bytes trajectory, drain on/off as configured.
- Did **not** claim a universal 3k RPS SLO; ceiling depends on host and stack depth.
