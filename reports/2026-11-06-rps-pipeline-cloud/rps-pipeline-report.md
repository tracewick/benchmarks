# Report: rps-pipeline — 2026-11-06

Methodology: [METHOD.md](../../METHOD.md) (high-RPS pipeline / spool). Limitations: [LIMITATIONS.md](../../LIMITATIONS.md).

Raw artifacts: this directory (run id `rps-pipeline-20261106T214258Z`).

## Scope

- PHP-FPM + `UnitOfWorkProfiler` + `SpoolSink` + drain (unless drain=off).
- Path `/work` with `WORK_STACK_DEPTH=48` (deeper stacks → larger spool payloads; wall budget still `WORK_BUSY_MS`).
- Not ContinuousProfiler / RoadRunner / go-agent.
- **Single-instance** host ceiling only (app + drain + Pyroscope + k6 colocated).

## Identity

| Field | Value |
| --- | --- |
| Date (UTC) | 2026-11-06T21:48:03Z |
| This repo SHA | `e4f6ab7c061f527d6a210daa86ccbbefa7312096` |
| Host | Linux nsk-1-vm-tsr3 7.0.0-42-generic #42-Ubuntu SMP PREEMPT_DYNAMIC Thu Oct 15 08:06:44 UTC 2026 x86_64 GNU/Linux |
| Host size | 8 vCPU / ~11–12 GiB |
| Make target | `make bench-rps` |

## Pins

| Component | Value |
| --- | --- |
| RATE (target) | 700 req/s |
| DURATION | 5m |
| sampleRate | 0.1 |
| WORK_STACK_DEPTH | 48 |
| PHP_FPM_MAX_CHILDREN | 32 |
| spool max_files | 500 (soft) |
| drain | on |
| PATH | /work |

## k6

| Metric | Value |
| --- | --- |
| Achieved RPS | 697.5729338044807 |
| http_req_failed | 0.000% |
| Latency med | 41.28 ms |
| Latency p95 | 50.99 ms |
| Latency p99 | 58.09 ms |

## Spool pipeline

| Metric | Value |
| --- | --- |
| Samples | 124 |
| Files max / last | 602 / 600 |
| Bytes max / last | 1.09 MiB / 1.09 MiB |

Steady ~600 files with drain on = soft admission + saturated PHP drain (fail-open), not a hard-cap defect. go-agent is expected to raise headroom later.

## What we proved / did not measure

- Pipeline under this arrival rate: HTTP fail-open, spool files/bytes trajectory, drain on as configured.
- Did **not** claim a universal 3k RPS SLO; ceiling depends on host and stack depth (~700 clean hold on this 8-vCPU stand; overload probes ~760 with multi-second latency).
