# Report: smoke — 2026-11-03

Methodology: [METHOD.md](../METHOD.md). Limitations: [LIMITATIONS.md](../LIMITATIONS.md).

Sample smoke run so a stranger can compare after `make up && make bench-smoke`.

## Identity

| Field | Value |
| --- | --- |
| Date (UTC) | 2026-11-03 |
| This repo SHA | `3940d62` (pre-M1 commit; regenerate SHA on your run) |
| Tracewick version | Packagist `0.1.0` |
| Host | Apple MacBook Pro, Darwin 25.6.0, arm64 (local laptop — not the cloud golden host) |
| Make target | `make bench-smoke` |

## Pins

| Component | Version |
| --- | --- |
| k6 image | `grafana/k6:1.8.2` |
| PHP / Excimer | 8.4 / 1.2.6 |
| Pyroscope | `grafana/pyroscope:2.4.2` |
| Grafana | `grafana/grafana:13.3.0` |
| sampleRate | `1.0` (smoke default; M2 will use `0.1`) |
| VUs / duration / BASE_URL | 5 / 45s / `http://127.0.0.1:8080` |
| WORK_BUSY_MS / WORK_SLEEP_MS | 25 / 10 |

## Results

### A. Application (smoke only — not an overhead A/B)

| Metric | Value |
| --- | --- |
| http_req_failed | 0% |
| checks | 1880/1880 passed |
| iterations | 939 |
| Latency p50 / p95 / max | ~39.2 ms / ~41.9 ms / ~74.7 ms |
| Approx RPS | ~21 |

### B. Pipeline

| Metric | Value |
| --- | --- |
| Spool → drain → Pyroscope | Profiles present after smoke |
| Pyroscope `service_name` | `benchmarks-workload` |
| Pyroscope `route` | `work` |

### C. Signal

Grafana: http://127.0.0.1:3000 → Explore / Drilldown → Profiles → service `benchmarks-workload`.

## What we proved / did not measure

- Proved: clone-style stand path works; k6 thresholds hold; profiles reach Pyroscope via SpoolSink + `tracewick-drain`.
- Did **not** measure: baseline vs on overhead, soak / 72h RSS, chaos, multi-host isolation.
- Host was a developer laptop sharing CPU with the IDE — treat numbers as a wiring sample, not a capacity claim.
