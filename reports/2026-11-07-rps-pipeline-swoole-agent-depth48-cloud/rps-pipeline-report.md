# Report: rps-pipeline — 2026-11-07

Methodology: [METHOD.md](../../METHOD.md) (high-RPS pipeline / spool). Limitations: [LIMITATIONS.md](../../LIMITATIONS.md).

Raw artifacts: `rps-pipeline-20261107T005129Z/`.

## Scope

- Swoole + `ContinuousProfiler` + `SpoolSink` + reader=`agent`.
- Path `/work` with `WORK_STACK_DEPTH=48` (deeper stacks → larger spool payloads; wall budget still `WORK_BUSY_MS`).
- **Single instance:** sustained RPS is the ceiling of this host + work unit + worker pool (often co-located k6), not a universal Tracewick SLO or multi-node fleet result.
- Not PHP-FPM / RoadRunner UnitOfWorkProfiler.

## Identity

| Field | Value |
| --- | --- |
| Date (UTC) | 2026-11-07T00:56:39Z |
| This repo SHA | `c81d1d93b6eb936b901ccaf7446d517a3556c344` |
| Host | Linux nsk-1-vm-tsr3 7.0.0-42-generic #42-Ubuntu SMP PREEMPT_DYNAMIC Thu Oct 15 08:06:44 UTC 2026 x86_64 GNU/Linux |
| Make target | `make bench-rps` |

## Pins

| Component | Value |
| --- | --- |
| RATE (target) | 700 req/s |
| DURATION | 5m |
| sampleRate | n/a (ContinuousProfiler always-on) |
| WORK_STACK_DEPTH | 48 |
| RUNTIME | swoole |
| SWOOLE_WORKER_NUM | 32 |
| READER | agent |
| PATH | /work |

## k6

| Metric | Value |
| --- | --- |
| Achieved RPS | 697.4983208361066 |
| http_req_failed | 0.000% |
| Latency med | 42.11 ms |
| Latency p95 | 73.22 ms |
| Latency p99 | 97.14 ms |

## Spool pipeline

| Metric | Value |
| --- | --- |
| Samples | 124 |
| Files max / last | 32 / 0 |
| Bytes max / last | 0.25 MiB / 0.00 MiB |

## What we proved / did not measure

- Pipeline under this arrival rate: HTTP fail-open, spool files/bytes trajectory, drain on/off as configured.
- Did **not** claim a universal 3k RPS SLO; ceiling depends on host and stack depth.
