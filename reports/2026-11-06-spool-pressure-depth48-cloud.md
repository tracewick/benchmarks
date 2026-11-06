# Report: spool pressure — 2026-11-06 (depth-48)

Methodology: [METHOD.md](../METHOD.md) layer B. Limitations: [LIMITATIONS.md](../LIMITATIONS.md).

Raw artifacts: [2026-11-06-spool-pressure-depth48-cloud/](./2026-11-06-spool-pressure-depth48-cloud/).

Sibling of [2026-11-03-spool-pressure-cloud.md](./2026-11-03-spool-pressure-cloud.md) (shallow). Same soft `max_files=80` fill; depth-48 makes each spool file ~**4.7×** larger in bytes.

## Setup

| Field | Value |
| --- | --- |
| Host | Timeweb `nsk-1-vm-tsr3` (**8 vCPU** stand) |
| repo SHA | `a5e2560cda67cf4ebbe2460726c18beccc4e8559` |
| sampleRate | `1.0` (fill spool faster) |
| `TRACEWICK_SPOOL_MAX_FILES` | `80` |
| WORK_STACK_DEPTH | **48** |
| RATE / duration | 20 req/s / 90s |
| Drain during load | **stopped** |

## Results

| Metric | Value |
| --- | --- |
| Peak spool files | **80 / 80** (hit soft admission ceiling) |
| Peak spool bytes | **170 769** (~0.16 MiB; ~2.1 KiB/file) |
| Shallow golden peak bytes (ref) | ~37 KiB (~0.46 KiB/file) |
| HTTP fail rate during fill | **0%** |
| Achieved RPS | ~19.8 |
| Drain catch-up after restart | **40 s** to empty |

## Verdict

Fail-open holds with realistic stack depth: app stayed green while spool filled to the configured file ceiling (further profiles dropped at admission). Bytes per file grew ~4.7× vs shallow; catch-up lag stayed ~40 s on this stand (vs ~41 s shallow). Matches M3 intent under deeper profiles.
