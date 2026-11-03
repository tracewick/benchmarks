# Measurement methodology

Canon for every scenario and report in this repository.
Derived from the Tracewick benchmarks Docmost brief (§2.6).

Reports and scenarios **must** link back to this document.

## What we measure (three layers)

### A. Application overhead

Same workload, A/B comparison:

| Metric | Why |
| --- | --- |
| Latency p50 / p95 / p99 (HTTP or job duration) | Request slowdown |
| Throughput (RPS / jobs/s) | Whether target load is sustained |
| CPU % of PHP (FPM / worker) | Sampling cost |
| RSS / memory growth | Buffers / leaks |

Runs: **baseline** (Tracewick off / kill switch) vs **on** at a pinned `sampleRate` (default for golden runs: `0.1`).

### B. Tracewick pipeline (spool → drain → Pyroscope)

| Metric | Why |
| --- | --- |
| Spool file count / bytes | Queue growth |
| Drain lag | Delivery backlog |
| Drops / rejects (diagnostics) | Soft admission, cardinality |
| Errors / retries toward Pyroscope | Resilience under degradation |

### C. Signal (spot checks)

Profiles arrive in Pyroscope within the run window; sample volume is consistent with order-of-magnitude `RPS × sampleRate`.
We do **not** claim exact per-symbol CPU percentages.

## Tools

| Tool | Role |
| --- | --- |
| **k6** (primary generator; alternatives only with written justification) | Load, latency, RPS |
| docker stats / cgroup / `pidstat` | CPU / RSS for PHP and drain |
| Tracewick diagnostics counters | Drops, failures |
| `du` / spool file counts | Disk pressure |
| Pyroscope + Grafana | Profile presence; screenshots for reports |
| Toxiproxy (optional) | Latency / 5xx toward Pyroscope |

Pinned image / binary versions live in `compose.yaml`, the Makefile (`K6_IMAGE`), and each report's parameter block.

## How we run

1. **Pin:** Tracewick tag/commit, PHP / Pyroscope / Grafana images, k6 version, CPU limits if any.
2. **Warmup**, then a fixed window (smoke: 5–15 minutes; soak: `make bench-soak`, default 72h at moderate RPS — RSS/CPU series, not an overhead table).
3. **One factor per run:** baseline vs on; separately spool pressure; separately chaos; separately soak. Do not mix.
4. **Same load script** (URL, VUs, duration) across the A/B pair.
5. **Report** = parameters + table + 1–2 screenshots + “what we proved / what we did not measure”.
6. A stranger repeats with `make up` → `make bench-…` and compares against a sample report in git.

## Explicit non-goals (v1)

- Absolute “overhead < X% on any hardware” without host caveats.
- Marketing bake-off vs Arc Lamp / Excimetry.
- Host-wide cardinality / multi-host without a dedicated scenario.
- Replacing library correctness CI (PHPStan / Infection / unit tests).

## Report template

Use `reports/TEMPLATE.md`. Every checked-in report should record:

- Host description (CPU, RAM, OS) and git SHAs of this repo and Tracewick
- Scenario name and Make target
- Pin table (images, Tracewick version, k6, sampleRate, VUs, duration)
- Metric table for layers A/B (and C if checked)
- Screenshots (relative paths under `reports/…`)
- Honesty paragraph: what was *not* measured
