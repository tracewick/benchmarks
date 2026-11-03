# Report: overhead A/B — 2026-11-03

Methodology: [METHOD.md](../METHOD.md). Limitations: [LIMITATIONS.md](../LIMITATIONS.md).

## Identity

| Field | Value |
| --- | --- |
| Date (UTC) | 2026-11-03 |
| This repo SHA | `26515058e2cec985db4c51278b412d7db52c2799` |
| Tracewick version | Packagist `0.1.0` |
| Host | Linux nsk-1-vm-tsr3 7.0.0-42-generic #42-Ubuntu SMP PREEMPT_DYNAMIC Thu Oct 15 08:06:44 UTC 2026 x86_64 GNU/Linux |
| Make target | `make bench-overhead` |

## Pins

| Component | Version |
| --- | --- |
| k6 image | `grafana/k6:1.8.2` |
| PHP / Excimer | 8.4 / 1.2.6 |
| Pyroscope | `grafana/pyroscope:2.4.2` |
| sampleRate (on) | `0.1` |
| baseline | `TRACEWICK_ENABLED=0` (profiler not constructed) |
| RATE / duration | 20 req/s / 2m |
| WORK_BUSY_MS / WORK_SLEEP_MS | 25 / 10 |

## Results — A. Application overhead

| Metric | baseline (off) | on (0.1) | delta (on − baseline) |
| --- | --- | --- | --- |
| Latency med | 37.64 ms | 38.19 ms | +0.55 ms |
| Latency p95 | 38.85 ms | 40.25 ms | +1.40 ms |
| Latency p99 | 40.76 ms | 42.17 ms | +1.41 ms |
| HTTP RPS (achieved) | 19.843512894789157 | 19.841382257798816 | |
| http_req_failed | None | None | |
| app-fpm CPU avg | 51.688% | 53.795% | +2.107 pp |
| app-fpm CPU max | 62.880% | 66.170% | +3.290 pp |
| app-fpm RSS avg | 12.2 MiB | 22.1 MiB | |
| app-fpm RSS max | 12.4 MiB | 27.5 MiB | |

Stats samples: baseline=39, on=39 (docker stats on `app-fpm`).

## What we proved / did not measure

- Proved: relative overhead of Tracewick SpoolSink path vs profiler-not-wired on this synthetic `/work` unit at fixed arrival rate.
- Did **not** measure: real app (DB/HTTP), soak/72h RSS growth, spool backpressure, chaos, multi-host isolation.
- Absolute % is host-specific; compare delta columns, not marketing SLOs.

