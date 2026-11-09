# Report: soak — 2026-11-08

Methodology: [METHOD.md](../../METHOD.md) (soak / RSS·CPU growth). Limitations: [LIMITATIONS.md](../../LIMITATIONS.md).

Raw artifacts: `soak-20261108T092931Z/`.

## Identity

| Field | Value |
| --- | --- |
| Date (UTC) | 2026-11-08T15:31:17Z |
| This repo SHA | `8f7e3725c0b20f452d6b500ad01e6800ca636f06` |
| Tracewick version | Packagist `0.1.0` (stand pin) |
| Host | Linux nsk-1-vm-tsr3 7.0.0-42-generic #42-Ubuntu SMP PREEMPT_DYNAMIC Thu Oct 15 08:06:44 UTC 2026 x86_64 GNU/Linux |
| Make target | `make bench-soak` |

## Pins

| Component | Value |
| --- | --- |
| k6 image | `grafana/k6:1.8.2` |
| RUNTIME | `rr` (RoadRunner) |
| Profiler | `UnitOfWorkProfiler` + `SpoolSink` |
| READER | `agent` |
| WORK_STACK_DEPTH | 48 |
| RATE | 10 req/s |
| DURATION | 6h |
| sampleRate | 0.1 |
| STATS_INTERVAL | see run meta / CSV spacing |

## k6 (layer A, soak window)

| Metric | Value |
| --- | --- |
| Achieved RPS | 9.999603264432677 |
| http_req_failed | 0.000% |
| Latency med | 36.79 ms |
| Latency p95 | 37.04 ms |
| Latency p99 | 37.21 ms |

## RSS / CPU time series

| Service | Samples | Hours | RSS first→last | Δ RSS | Δ % | RSS min/max | CPU avg/max | Verdict |
| --- | ---: | ---: | --- | --- | ---: | --- | --- | --- |
| app-rr | 355 | 6.01 | 95.23 MiB → 98.59 MiB | 3.36 MiB | 3.53 | 68.66 MiB / 100.90 MiB | 27.399 / 33.99 | stable (within noise) |
| app-agent | 355 | 6.01 | 15.41 MiB → 17.78 MiB | 2.37 MiB | 15.37 | 12.85 MiB / 18.71 MiB | 0.081 / 0.51 | stable (within noise) |

## What we proved / did not measure

- Proved (if verdicts stable): no large RSS climb on `app-rr` / `app-agent` (RoadRunner + `UnitOfWorkProfiler`, reader=`agent`) under moderate fixed RPS for the soak window.
- Did **not** measure: overhead A/B deltas, spool chaos, 1k+ RPS ceiling, multi-host isolation.
