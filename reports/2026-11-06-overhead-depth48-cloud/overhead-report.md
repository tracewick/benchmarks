# Report: overhead A/B — 2026-11-06

Methodology: [METHOD.md](../METHOD.md). Limitations: [LIMITATIONS.md](../LIMITATIONS.md).

## Identity

| Field | Value |
| --- | --- |
| Date (UTC) | 2026-11-06 |
| This repo SHA | `a5e2560cda67cf4ebbe2460726c18beccc4e8559` |
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
| WORK_STACK_DEPTH | 48 |

## Results — A. Application overhead

| Metric | baseline (off) | on (0.1) | delta (on − baseline) |
| --- | --- | --- | --- |
| Latency med | 36.16 ms | 36.64 ms | +0.48 ms |
| Latency p95 | 36.42 ms | 37.80 ms | +1.39 ms |
| Latency p99 | 36.57 ms | 38.23 ms | +1.66 ms |
| HTTP RPS (achieved) | 19.844478618655224 | 19.842215499671457 | |
| http_req_failed | 0.0 | 0.0 | |
| app-fpm CPU avg | 50.319% | 51.437% | +1.118 pp |
| app-fpm CPU max | 57.320% | 58.000% | +0.680 pp |
| app-fpm RSS avg | 13.2 MiB | 14.5 MiB | |
| app-fpm RSS max | 13.8 MiB | 15.1 MiB | |

Stats samples: baseline=40, on=40 (docker stats on `app-fpm`).

## What we proved / did not measure

- Proved: relative overhead of Tracewick SpoolSink path vs profiler-not-wired on this synthetic `/work` unit at fixed arrival rate.
- WORK_STACK_DEPTH=48: 0 = shallow busyWork; >0 = deeper frames (larger profiles, same wall budget).
- Did **not** measure: real app (DB/HTTP), soak/72h RSS growth, spool backpressure, chaos, multi-host isolation.
- Absolute % is host-specific; compare delta columns, not marketing SLOs.

