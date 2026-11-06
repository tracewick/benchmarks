# Report: overhead A/B — 2026-11-03 (Timeweb Cloud) — historical

> **Not canonical.** Shallow `WORK_STACK_DEPTH=0` on 2 vCPU. Cite instead: [2026-11-06-overhead-depth48-cloud.md](./2026-11-06-overhead-depth48-cloud.md).

Methodology: [METHOD.md](../METHOD.md). Limitations: [LIMITATIONS.md](../LIMITATIONS.md).

Raw k6 + `docker stats` samples: [2026-11-03-overhead-cloud/](./2026-11-03-overhead-cloud/).

## Identity

| Field | Value |
| --- | --- |
| Date (UTC) | 2026-11-03 |
| This repo SHA | `2651505` (run tooling) |
| Tracewick version | Packagist `0.1.0` |
| Host | Timeweb Cloud VPS `nsk-1-vm-tsr3`, Linux x86_64, Premium NVMe **2×3.3 GHz / 4 GB / 50 GB** |
| Make target | `make bench-overhead` |

## Pins

| Component | Version |
| --- | --- |
| k6 image | `grafana/k6:1.8.2` |
| PHP / Excimer | 8.4 / 1.2.6 |
| Pyroscope | `grafana/pyroscope:2.4.2` |
| sampleRate (on) | `0.1` |
| baseline | `TRACEWICK_ENABLED=0` (profiler not constructed) |
| RATE / duration | 20 req/s / 2m each arm |
| WORK_BUSY_MS / WORK_SLEEP_MS | 25 / 10 |

## Results — A. Application overhead

| Metric | baseline (off) | on (0.1) | delta (on − baseline) |
| --- | --- | --- | --- |
| Latency med | 37.64 ms | 38.19 ms | **+0.55 ms** |
| Latency p95 | 38.85 ms | 40.25 ms | **+1.40 ms** |
| Latency p99 | 40.76 ms | 42.17 ms | **+1.41 ms** |
| HTTP RPS (achieved) | 19.84 | 19.84 | held target |
| http_req_failed | 0% | 0% | |
| app-fpm CPU avg | 51.69% | 53.80% | **+2.11 pp** |
| app-fpm CPU max | 62.88% | 66.17% | **+3.29 pp** |
| app-fpm RSS avg | 12.2 MiB | 22.1 MiB | +~10 MiB |
| app-fpm RSS max | 12.4 MiB | 27.5 MiB | +~15 MiB |

Stats samples: 39 per arm (`docker stats` on `app-fpm`).

## Interpretation

- At **20 RPS** and **sampleRate 0.1** on this synthetic `/work` unit, Tracewick SpoolSink adds roughly **+0.5–1.4 ms** latency and about **+2 pp** PHP-FPM CPU vs profiler-not-wired.
- RSS rises (~10–15 MiB) with profiling on; absolute footprint stays small on this workload.
- Both arms sustained the arrival rate with **0%** HTTP failures.
- These are **relative** figures on a shared 2 vCPU box with Pyroscope/Grafana/drain co-located — not a universal SLO.

## What we proved / did not measure

- Proved: measurable but modest overhead for SpoolSink path vs off at fixed RPS on commodity cloud VPS.
- Did **not** measure: real app (DB/HTTP), 1k–5k RPS ceiling, soak/72h growth, spool backpressure, chaos, isolated k6 host.
