# Report: chaos Pyroscope latency — 2026-11-06 (depth-48) — canonical

Methodology: [METHOD.md](../METHOD.md) layer B. Limitations: [LIMITATIONS.md](../LIMITATIONS.md).

Raw artifacts: [2026-11-06-chaos-pyroscope-depth48-cloud/](./2026-11-06-chaos-pyroscope-depth48-cloud/).

**Canonical** chaos golden. Historical shallow: [2026-11-03-chaos-pyroscope-cloud.md](./2026-11-03-chaos-pyroscope-cloud.md). Same Toxiproxy latency toxic; depth-48 raises bytes behind the soft file ceiling.

## Setup

| Field | Value |
| --- | --- |
| Host | Timeweb `nsk-1-vm-tsr3` (**8 vCPU** stand) |
| repo SHA | `a5e2560cda67cf4ebbe2460726c18beccc4e8559` |
| Toxic | Toxiproxy **3000 ms** latency on path drain → Pyroscope |
| sampleRate | `1.0` |
| WORK_STACK_DEPTH | **48** |
| RATE / duration | 20 req/s / 60s |
| Drain URL | `http://toxiproxy:14040` |

## Results

| Metric | Value |
| --- | --- |
| Peak spool files during toxic | **500** (default `max_files`) |
| Peak spool bytes | **1 085 178** (~1.03 MiB; ~2.2 KiB/file) |
| Shallow golden peak bytes (ref) | ~221 KiB (~0.45 KiB/file) |
| HTTP fail rate | **0%** |
| k6 thresholds | passed (`k6_rc=0`) |

## Verdict

Backend degradation still does not take down the request path: latency toxic stalled delivery and filled the soft file ceiling while `/work` stayed healthy. Depth-48 multiplies bytes (~4.8× vs shallow) without changing the fail-open story.
