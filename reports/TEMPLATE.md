# Report: \<scenario\> — \<YYYY-MM-DD\>

Methodology: [METHOD.md](../METHOD.md). Limitations: [LIMITATIONS.md](../LIMITATIONS.md).

## Identity

| Field | Value |
| --- | --- |
| Date (UTC) | |
| This repo SHA | |
| Tracewick version / SHA | |
| Host | CPU / RAM / OS |
| Make target | `bench-…` |

## Pins

| Component | Version |
| --- | --- |
| k6 image | `grafana/k6:1.8.2` |
| PHP / Excimer | |
| Pyroscope | `grafana/pyroscope:2.4.2` |
| Grafana | `grafana/grafana:13.3.0` |
| sampleRate | |
| VUs / duration / BASE_URL | |

## Results

### A. Application overhead

| Metric | baseline | on | Notes |
| --- | --- | --- | --- |
| Latency p50 / p95 / p99 | | | |
| Throughput | | | |
| CPU % PHP | | | |
| RSS | | | |

### B. Pipeline

| Metric | Value | Notes |
| --- | --- | --- |
| Spool files / bytes | | |
| Drain lag | | |
| Drops / rejects | | |
| Pyroscope errors / retries | | |

### C. Signal (optional)

Profiles visible in Grafana/Pyroscope within the window? Order-of-magnitude samples vs `RPS × sampleRate`?

## Screenshots

- `./…png`

## What we proved / did not measure

-
