# Report: soak — 2026-11-06

Methodology: [METHOD.md](../../METHOD.md) (soak / RSS·CPU growth). Limitations: [LIMITATIONS.md](../../LIMITATIONS.md).

Raw artifacts: `soak-20261103T105644Z/`.

## Identity

| Field | Value |
| --- | --- |
| Date (UTC) | 2026-11-06T10:57:59Z |
| This repo SHA | `9c1c9efd28fab0a8a69164e14ec9eef37f2929ea` |
| Tracewick version | Packagist `0.1.0` (stand pin) |
| Host | Linux nsk-1-vm-tsr3 7.0.0-42-generic #42-Ubuntu SMP PREEMPT_DYNAMIC Thu Oct 15 08:06:44 UTC 2026 x86_64 GNU/Linux |
| Make target | `make bench-soak` |

## Pins

| Component | Value |
| --- | --- |
| k6 image | `grafana/k6:1.8.2` |
| RATE | 10 req/s |
| DURATION | 72h |
| sampleRate | 0.1 |
| STATS_INTERVAL | see run meta / CSV spacing |

## k6 (layer A, soak window)

| Metric | Value |
| --- | --- |
| Achieved RPS | 9.999967432799053 |
| http_req_failed | 0.000% |
| Latency med | 37.85 ms |
| Latency p95 | 39.56 ms |
| Latency p99 | 40.23 ms |

## RSS / CPU time series

| Service | Samples | Hours | RSS first→last | Δ RSS | Δ % | RSS min/max | CPU avg/max | Verdict |
| --- | ---: | ---: | --- | --- | ---: | --- | --- | --- |
| app-fpm | 4238 | 72.003 | 35.48 MiB → 35.63 MiB | 0.15 MiB | 0.41 | 32.42 MiB / 41.74 MiB | 27.988 / 52.13 | stable (within noise) |
| app-drain | 4238 | 72.002 | 69.62 MiB → 69.58 MiB | -0.04 MiB | -0.06 | 69.50 MiB / 70.48 MiB | 0.063 / 0.42 | stable (within noise) |

## What we proved / did not measure

- Proved (if verdicts stable): no large RSS climb on FPM/drain under moderate fixed RPS for the soak window.
- Did **not** measure: overhead A/B deltas, spool chaos, 1k+ RPS ceiling, multi-host isolation.
