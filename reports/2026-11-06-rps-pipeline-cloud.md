# Report: high-RPS pipeline — 2026-11-06 — canonical

Methodology: [METHOD.md](../METHOD.md) (high-RPS pipeline / spool). Limitations: [LIMITATIONS.md](../LIMITATIONS.md).

Raw artifacts: [2026-11-06-rps-pipeline-cloud/](./2026-11-06-rps-pipeline-cloud/).

## Identity

| Field | Value |
| --- | --- |
| Date (UTC) | 2026-11-06T21:48:03Z |
| This repo SHA | `e4f6ab7c061f527d6a210daa86ccbbefa7312096` |
| Tracewick version | Packagist `0.1.0` (stand pin) |
| Host | Linux nsk-1-vm-tsr3 7.0.0-42-generic #42-Ubuntu SMP PREEMPT_DYNAMIC Thu Oct 15 08:06:44 UTC 2026 x86_64 GNU/Linux |
| Make target | `make bench-rps` |

## Host

| Field | Value |
| --- | --- |
| VPS | Timeweb `nsk-1-vm-tsr3` |
| Size during run | **8 vCPU / ~11–12 GiB / ~96 GB** |
| Colocation | app-fpm + drain + Pyroscope + k6 on the **same** instance |

## Pins

| Component | Value |
| --- | --- |
| k6 image | `grafana/k6:1.8.2` |
| RATE (target) | 700 req/s |
| DURATION | 5m |
| REQUEST_PATH | `/work` |
| sampleRate | 0.1 |
| WORK_STACK_DEPTH | 48 |
| WORK_BUSY_MS / WORK_SLEEP_MS | 25 / 10 |
| PHP_FPM_MAX_CHILDREN | 32 (`pm=static`) |
| spool `max_files` | 500 (soft admission) |
| drain | on |

## k6 (layer A)

| Metric | Value |
| --- | --- |
| Achieved RPS | 697.57 |
| http_req_failed | 0.000% |
| checks | 420006 pass / 0 fail |
| Latency med / p95 / p99 | 41.28 / 50.99 / 58.09 ms |
| dropped_iterations | none (sufficient VUs) |

## Spool pipeline (layer B)

| Metric | Value |
| --- | --- |
| Samples | 124 (~2.5 s spacing over the hold) |
| Files max / last | **602 / 600** |
| Bytes max / last | **1.09 MiB / 1.09 MiB** |
| Steady state | last samples sit ~600 files (above soft `max_files=500`) |

Soft overshoot past 500 is expected under fail-open admission while drain is saturated: writers keep serving HTTP; further profiles may be dropped at admission once the soft ceiling is crossed. This is **not** a hard-cap bug.

## Scope

This run exercised **PHP-FPM only**:

- `pm=static`, 32 long-lived workers
- request path: **`UnitOfWorkProfiler` + `SpoolSink`** with depth-48 synthetic stacks (same wall budget as overhead/soak)
- delivery: long-lived **`tracewick-drain`** → Pyroscope

It does **not** cover RoadRunner, `ContinuousProfiler`, or go-agent. PHP drain is the reference reader; a future go-agent is expected to raise spool headroom on the same stand.

## Single-instance ceiling (honesty)

- Published **~700 RPS** is the **clean hold** for this host + work unit + FPM pool + colocated k6/Pyroscope — **not** a universal Tracewick SLO and **not** multi-node highload.
- Overload probes on the same box (1.5k–3k targets, short windows) peaked around **~760 achieved** with multi-second latency and dropped iterations — so 1.5k–3k is overload for this configuration, not a missed tuning knob.

## What we proved / did not measure

- Proved: depth-48 `/work` pipeline holds ~700 RPS with HTTP fail 0% and p99 ~58 ms; spool sits at soft-admission steady state (~600 files / ~1.1 MiB) with PHP drain on.
- Did **not** measure: drain=off admission stress golden, ContinuousProfiler / RR / go-agent throughput, multi-host isolation, K8s.
