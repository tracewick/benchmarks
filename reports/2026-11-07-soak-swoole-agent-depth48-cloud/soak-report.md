# Report: soak — 2026-11-07

Methodology: [METHOD.md](../../METHOD.md) (soak / RSS·CPU growth). Limitations: [LIMITATIONS.md](../../LIMITATIONS.md).

Raw artifacts: `soak-20261107T140855Z/`.

## Identity

| Field | Value |
| --- | --- |
| Date (UTC) | 2026-11-07T20:10:44Z |
| This repo SHA | `97fa542b791391dc15688bb57c5b2686aa02ef37` |
| Tracewick version | Packagist `0.1.0` (stand pin) |
| Host | Linux nsk-1-vm-tsr3 7.0.0-42-generic #42-Ubuntu SMP PREEMPT_DYNAMIC Thu Oct 15 08:06:44 UTC 2026 x86_64 GNU/Linux |
| Make target | `make bench-soak` |

## Pins

| Component | Value |
| --- | --- |
| k6 image | `grafana/k6:1.8.2` |
| RUNTIME | `swoole` (Swoole) |
| Profiler | `ContinuousProfiler` + `SpoolSink` |
| READER | `agent` |
| WORK_STACK_DEPTH | 48 |
| RATE | 10 req/s |
| DURATION | 6h |
| sampleRate | 0.1 |
| STATS_INTERVAL | see run meta / CSV spacing |

## k6 (layer A, soak window)

| Metric | Value |
| --- | --- |
| Achieved RPS | 9.999611293776704 |
| http_req_failed | 0.000% |
| Latency med | 35.89 ms |
| Latency p95 | 36.03 ms |
| Latency p99 | 36.12 ms |

## RSS / CPU time series

| Service | Samples | Hours | RSS first→last | Δ RSS | Δ % | RSS min/max | CPU avg/max | Verdict |
| --- | ---: | ---: | --- | --- | ---: | --- | --- | --- |
| app-swoole | 355 | 6.011 | 23.32 MiB → 25.23 MiB | 1.92 MiB | 8.23 | 21.09 MiB / 28.86 MiB | 29.726 / 38.84 | stable (within noise) |
| app-agent | 355 | 6.011 | 12.93 MiB → 14.50 MiB | 1.57 MiB | 12.15 | 10.54 MiB / 15.36 MiB | 0.047 / 0.67 | stable (within noise) |

## What we proved / did not measure

- Proved (if verdicts stable): no large RSS climb on `app-swoole` / `app-agent` (Swoole + `ContinuousProfiler`, reader=`agent`) under moderate fixed RPS for the soak window.
- Did **not** measure: overhead A/B deltas, spool chaos, 1k+ RPS ceiling, multi-host isolation.
