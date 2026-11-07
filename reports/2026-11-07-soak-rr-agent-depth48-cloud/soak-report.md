# Report: soak — 2026-11-07

Methodology: [METHOD.md](../../METHOD.md) (soak / RSS·CPU growth). Limitations: [LIMITATIONS.md](../../LIMITATIONS.md).

Raw artifacts: `soak-20261107T080711Z/`.

## Identity

| Field | Value |
| --- | --- |
| Date (UTC) | 2026-11-07T14:08:55Z |
| This repo SHA | `97fa542b791391dc15688bb57c5b2686aa02ef37` |
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
| Achieved RPS | 9.999604353509438 |
| http_req_failed | 0.000% |
| Latency med | 36.89 ms |
| Latency p95 | 37.23 ms |
| Latency p99 | 37.45 ms |

## RSS / CPU time series

| Service | Samples | Hours | RSS first→last | Δ RSS | Δ % | RSS min/max | CPU avg/max | Verdict |
| --- | ---: | ---: | --- | --- | ---: | --- | --- | --- |
| app-rr | 355 | 6.01 | 207.97 MiB → 1189.32 MiB | 981.34 MiB | 471.87 | 66.23 MiB / 1236.99 MiB | 27.483 / 34.54 | growth concern |
| app-agent | 355 | 6.009 | 11.52 MiB → 10.12 MiB | -1.40 MiB | -12.17 | 9.71 MiB / 13.75 MiB | 0.057 / 0.46 | stable (within noise) |

## What we proved / did not measure

- Proved (if verdicts stable): no large RSS climb on `app-rr` / `app-agent` (RoadRunner + `UnitOfWorkProfiler`, reader=`agent`) under moderate fixed RPS for the soak window.
- Did **not** measure: overhead A/B deltas, spool chaos, 1k+ RPS ceiling, multi-host isolation.
