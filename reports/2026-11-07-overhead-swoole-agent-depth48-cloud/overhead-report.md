# Report: overhead A/B — 2026-11-07

Methodology: [METHOD.md](../METHOD.md). Limitations: [LIMITATIONS.md](../LIMITATIONS.md).

## Identity

| Field | Value |
| --- | --- |
| Date (UTC) | 2026-11-07 |
| This repo SHA | `6235303ad6cf599f0704cffb710331e3a6acff10` |
| Tracewick version | Packagist `0.1.0` |
| Host | Linux nsk-1-vm-tsr3 7.0.0-42-generic #42-Ubuntu SMP PREEMPT_DYNAMIC Thu Oct 15 08:06:44 UTC 2026 x86_64 GNU/Linux |
| Make target | `make bench-overhead` |

## Pins

| Component | Version |
| --- | --- |
| k6 image | `grafana/k6:1.8.2` |
| PHP / Excimer | 8.4 / 1.2.6 |
| Pyroscope | `grafana/pyroscope:2.4.2` |
| RUNTIME | `swoole` (Swoole) |
| Profiler | `ContinuousProfiler` + SpoolSink |
| READER | `agent` |
| sampleRate (on) | n/a (ContinuousProfiler always-on when enabled) |
| baseline | `TRACEWICK_ENABLED=0` (profiler not constructed) |
| RATE / duration | 20 req/s / 2m |
| WORK_BUSY_MS / WORK_SLEEP_MS | 25 / 10 |
| WORK_STACK_DEPTH | 48 |

## Results — A. Application overhead

| Metric | baseline (off) | on | delta (on − baseline) |
| --- | --- | --- | --- |
| Latency med | 35.62 ms | 35.56 ms | -0.06 ms |
| Latency p95 | 35.77 ms | 35.74 ms | -0.03 ms |
| Latency p99 | 35.84 ms | 35.87 ms | +0.03 ms |
| HTTP RPS (achieved) | 19.844847736465525 | 19.844811687429804 | |
| http_req_failed | 0.0 | 0.0 | |
| app-swoole CPU avg | 50.404% | 51.169% | +0.765 pp |
| app-swoole CPU max | 58.250% | 58.530% | +0.280 pp |
| app-swoole RSS avg | 12.8 MiB | 16.6 MiB | |
| app-swoole RSS max | 13.3 MiB | 17.2 MiB | |

Stats samples: baseline=40, on=40 (docker stats on `app-swoole`).

## What we proved / did not measure

- Proved: relative overhead of Tracewick SpoolSink path vs profiler-not-wired on this synthetic `/work` unit (Swoole).
- WORK_STACK_DEPTH=48: 0 = shallow busyWork; >0 = deeper frames (larger profiles, same wall budget).
- Did **not** measure: real app (DB/HTTP), soak/72h RSS growth, spool backpressure, chaos, multi-host isolation.
- Absolute % is host-specific; compare delta columns, not marketing SLOs.

