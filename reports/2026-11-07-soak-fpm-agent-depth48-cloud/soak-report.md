# Report: soak — 2026-11-07

Methodology: [METHOD.md](../../METHOD.md) (soak / RSS·CPU growth). Limitations: [LIMITATIONS.md](../../LIMITATIONS.md).

Raw artifacts: `soak-20261107T020523Z/`.

## Identity

| Field | Value |
| --- | --- |
| Date (UTC) | 2026-11-07T08:07:11Z |
| This repo SHA | `97fa542b791391dc15688bb57c5b2686aa02ef37` |
| Tracewick version | Packagist `0.1.0` (stand pin) |
| Host | Linux nsk-1-vm-tsr3 7.0.0-42-generic #42-Ubuntu SMP PREEMPT_DYNAMIC Thu Oct 15 08:06:44 UTC 2026 x86_64 GNU/Linux |
| Make target | `make bench-soak` |

## Pins

| Component | Value |
| --- | --- |
| k6 image | `grafana/k6:1.8.2` |
| RUNTIME | `fpm` (PHP-FPM) |
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
| Achieved RPS | 9.999581563372404 |
| http_req_failed | 0.000% |
| Latency med | 36.76 ms |
| Latency p95 | 37.98 ms |
| Latency p99 | 38.44 ms |

## RSS / CPU time series

| Service | Samples | Hours | RSS first→last | Δ RSS | Δ % | RSS min/max | CPU avg/max | Verdict |
| --- | ---: | ---: | --- | --- | ---: | --- | --- | --- |
| app-fpm | 355 | 6.009 | 18.97 MiB → 22.56 MiB | 3.59 MiB | 18.94 | 13.66 MiB / 26.87 MiB | 26.727 / 33.21 | stable (within noise) |
| app-agent | 355 | 6.009 | 8.01 MiB → 10.69 MiB | 2.68 MiB | 33.47 | 2.71 MiB / 11.37 MiB | 0.074 / 0.42 | stable (within noise) |

## What we proved / did not measure

- Proved (if verdicts stable): no large RSS climb on `app-fpm` / `app-agent` (PHP-FPM + `UnitOfWorkProfiler`, reader=`agent`) under moderate fixed RPS for the soak window.
- Did **not** measure: overhead A/B deltas, spool chaos, 1k+ RPS ceiling, multi-host isolation.
