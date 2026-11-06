# Report: chaos Pyroscope latency — 2026-11-03 (Timeweb Cloud)

Methodology: [METHOD.md](../METHOD.md) layer B. Raw artifacts: [2026-11-03-chaos-pyroscope-cloud/](./2026-11-03-chaos-pyroscope-cloud/).

Depth-48 remake: [2026-11-06-chaos-pyroscope-depth48-cloud.md](./2026-11-06-chaos-pyroscope-depth48-cloud.md).

## Setup

| Field | Value |
| --- | --- |
| Host | Timeweb VPS `nsk-1-vm-tsr3` (2×3.3 GHz / 4 GB) |
| Toxic | Toxiproxy **3000 ms** latency on path drain → Pyroscope |
| sampleRate | `1.0` |
| RATE / duration | 20 req/s / 60s |
| Drain URL | `http://toxiproxy:14040` |

## Results

| Metric | Value |
| --- | --- |
| Peak spool files during toxic | **500** (default `max_files`) |
| HTTP fail rate | **0%** |
| k6 thresholds | passed after nginx recreate fix |

## Verdict

Backend degradation does not take down request path: latency toxic on Pyroscope made delivery stall and spool grow, while `/work` stayed healthy. Aligns with fail-open / spool architecture.
