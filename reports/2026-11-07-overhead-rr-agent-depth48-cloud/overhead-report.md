# Report: overhead A/B — 2026-11-07

Methodology: [METHOD.md](../METHOD.md). Limitations: [LIMITATIONS.md](../LIMITATIONS.md).

## Identity

| Field | Value |
| --- | --- |
| Date (UTC) | 2026-11-07 |
| This repo SHA | `8d658ffbef34d0bb4fcc625299c6e411d6afc263` |
| Tracewick version | Packagist `0.1.0` |
| Host | Linux nsk-1-vm-tsr3 7.0.0-42-generic #42-Ubuntu SMP PREEMPT_DYNAMIC Thu Oct 15 08:06:44 UTC 2026 x86_64 GNU/Linux |
| Make target | `make bench-overhead` |

## Pins

| Component | Version |
| --- | --- |
| k6 image | `grafana/k6:1.8.2` |
| PHP / Excimer | 8.4 / 1.2.6 |
| Pyroscope | `grafana/pyroscope:2.4.2` |
| RUNTIME | `rr` (RoadRunner) |
| READER | `agent` |
| sampleRate (on) | `0.1` |
| baseline | `TRACEWICK_ENABLED=0` (profiler not constructed) |
| RATE / duration | 20 req/s / 2m |
| WORK_BUSY_MS / WORK_SLEEP_MS | 25 / 10 |
| WORK_STACK_DEPTH | 48 |

## Results — A. Application overhead

| Metric | baseline (off) | on (0.1) | delta (on − baseline) |
| --- | --- | --- | --- |
| Latency med | 36.60 ms | 36.76 ms | +0.16 ms |
| Latency p95 | 36.87 ms | 37.09 ms | +0.23 ms |
| Latency p99 | 37.10 ms | 37.39 ms | +0.28 ms |
| HTTP RPS (achieved) | 19.842087585726937 | 19.84192927308932 | |
| http_req_failed | 0.0 | 0.0 | |
| app-rr CPU avg | 52.184% | 52.872% | +0.688 pp |
| app-rr CPU max | 59.390% | 60.070% | +0.680 pp |
| app-rr RSS avg | 52.5 MiB | 63.0 MiB | |
| app-rr RSS max | 56.0 MiB | 74.4 MiB | |

Stats samples: baseline=40, on=40 (docker stats on `app-rr`).

## What we proved / did not measure

- Proved: relative overhead of Tracewick SpoolSink path vs profiler-not-wired on this synthetic `/work` unit (RoadRunner).
- WORK_STACK_DEPTH=48: 0 = shallow busyWork; >0 = deeper frames (larger profiles, same wall budget).
- Did **not** measure: real app (DB/HTTP), soak/72h RSS growth, spool backpressure, chaos, multi-host isolation.
- Absolute % is host-specific; compare delta columns, not marketing SLOs.

