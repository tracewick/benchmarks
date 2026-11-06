# Report: spool pressure — 2026-11-06 (agent, depth-48) — canonical reader A/B

Methodology: [METHOD.md](../METHOD.md) layer B. Limitations: [LIMITATIONS.md](../LIMITATIONS.md).

Raw artifacts: [2026-11-06-spool-pressure-agent-depth48-cloud/](./2026-11-06-spool-pressure-agent-depth48-cloud/).

Same fill as [drain depth-48](./2026-11-06-spool-pressure-depth48-cloud.md); catch-up reader = **go-agent 0.1.0**.

## Setup

| Field | Value |
| --- | --- |
| Host | Timeweb `nsk-1-vm-tsr3` (**8 vCPU**) |
| repo SHA | `e9c36a0fc007d73d5c5e392db328869350df5190` |
| sampleRate | `1.0` |
| `TRACEWICK_SPOOL_MAX_FILES` | `80` |
| WORK_STACK_DEPTH | **48** |
| Catch-up reader | **`agent`** (`ghcr`/release `0.1.0`, UID 33) |
| RATE / duration | 20 req/s / 90s |
| Reader during load | **stopped** |

## Results

| Metric | agent | drain (depth-48 ref) |
| --- | --- | --- |
| Peak spool files | **80 / 80** | 80 / 80 |
| Peak spool bytes | ~0.17 MiB | ~0.16 MiB |
| HTTP fail during fill | **0%** | 0% |
| Catch-up to empty | **2 s** | **40 s** |

## Verdict

Fail-open unchanged. Agent clears the same 80-file soft ceiling ~**20×** faster than PHP drain on this stand.
