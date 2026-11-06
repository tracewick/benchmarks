# Report: overhead A/B — 2026-11-06 (depth-48)

Methodology: [METHOD.md](../METHOD.md). Limitations: [LIMITATIONS.md](../LIMITATIONS.md).

Raw artifacts: [2026-11-06-overhead-depth48-cloud/](./2026-11-06-overhead-depth48-cloud/).

Sibling of the shallow golden [2026-11-03-overhead-cloud.md](./2026-11-03-overhead-cloud.md) (`WORK_STACK_DEPTH=0` on 2 vCPU). This remake uses **depth-48** stacks on the **8 vCPU** stand so profile payloads match high-RPS work shape. Do not treat host-size change and depth change as one factor.

## Identity

| Field | Value |
| --- | --- |
| Date (UTC) | 2026-11-06 |
| This repo SHA | `a5e2560cda67cf4ebbe2460726c18beccc4e8559` |
| Tracewick version | Packagist `0.1.0` |
| Host | Timeweb `nsk-1-vm-tsr3`, Linux x86_64 — **8 vCPU / ~11–12 GiB** |
| Make target | `WORK_STACK_DEPTH=48 make bench-overhead` |

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
| WORK_STACK_DEPTH | **48** |
| PHP_FPM_MAX_CHILDREN | 4 (`pm=static`) |

## Results — A. Application overhead

| Metric | baseline (off) | on (0.1) | delta (on − baseline) |
| --- | --- | --- | --- |
| Latency med | 36.16 ms | 36.64 ms | **+0.48 ms** |
| Latency p95 | 36.42 ms | 37.80 ms | **+1.39 ms** |
| Latency p99 | 36.57 ms | 38.23 ms | **+1.66 ms** |
| HTTP RPS (achieved) | 19.84 | 19.84 | held target |
| http_req_failed | 0% | 0% | |
| app-fpm CPU avg | 50.32% | 51.44% | **+1.12 pp** |
| app-fpm CPU max | 57.32% | 58.00% | **+0.68 pp** |
| app-fpm RSS avg | 13.2 MiB | 14.5 MiB | +~1.3 MiB |
| app-fpm RSS max | 13.8 MiB | 15.1 MiB | +~1.3 MiB |

Stats samples: 40 per arm (`docker stats` on `app-fpm`).

## Interpretation

- On depth-48 `/work` at **20 RPS** / **sampleRate 0.1**, Tracewick SpoolSink still adds roughly **+0.5–1.7 ms** latency and about **+1 pp** FPM CPU vs profiler-not-wired — same order as the shallow 2 vCPU golden.
- Absolute latency is slightly lower than the Nov-3 2 vCPU run (host upsizing); **compare delta columns**, not absolute ms across hosts.
- Both arms held arrival rate with **0%** HTTP failures.

## What we proved / did not measure

- Proved: modest relative overhead remains with deeper stacks / larger profiles on this stand.
- Did **not** measure: real app, soak growth under depth-48, isolated generator host.
