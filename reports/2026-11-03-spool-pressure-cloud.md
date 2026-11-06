# Report: spool pressure — 2026-11-03 (Timeweb Cloud)

Methodology: [METHOD.md](../METHOD.md) layer B. Raw artifacts: [2026-11-03-spool-pressure-cloud/](./2026-11-03-spool-pressure-cloud/).

Depth-48 remake: [2026-11-06-spool-pressure-depth48-cloud.md](./2026-11-06-spool-pressure-depth48-cloud.md).

## Setup

| Field | Value |
| --- | --- |
| Host | Timeweb VPS `nsk-1-vm-tsr3` (2×3.3 GHz / 4 GB) |
| sampleRate | `1.0` (fill spool faster) |
| `TRACEWICK_SPOOL_MAX_FILES` | `80` |
| RATE / duration | 20 req/s / 90s |
| Drain during load | **stopped** |

## Results

| Metric | Value |
| --- | --- |
| Peak spool files | **80 / 80** (hit soft admission ceiling) |
| HTTP fail rate during fill | **0%** |
| Achieved RPS | ~19.8 |
| Drain catch-up after restart | **41 s** to empty |

## Verdict

Fail-open holds: app stayed green while spool filled to the configured ceiling (further profiles dropped at admission). After drain restart, queue cleared in ~41s. Matches M3 intent.
