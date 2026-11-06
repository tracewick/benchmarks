# Report: spool pressure — 2026-11-06

Methodology: [METHOD.md](../../METHOD.md) layer B.

## Setup

| Field | Value |
| --- | --- |
| Host run dir | `/root/benchmarks/reports/_local/spool-pressure-20261106T223230Z` |
| Host | Linux nsk-1-vm-tsr3 7.0.0-42-generic #42-Ubuntu SMP PREEMPT_DYNAMIC Thu Oct 15 08:06:44 UTC 2026 x86_64 GNU/Linux |
| repo SHA | `a5e2560cda67cf4ebbe2460726c18beccc4e8559` |
| sampleRate | `1.0` |
| TRACEWICK_SPOOL_MAX_FILES | `80` |
| WORK_STACK_DEPTH | 48 |
| RATE / duration | 20 / 90s |
| Drain during load | **stopped** |

## Results

| Metric | Value |
| --- | --- |
| Peak spool files | 80 (cap 80) |
| Peak spool bytes | 170769 (0.16 MiB) |
| HTTP fail rate during fill | 0 |
| Achieved RPS | 19.793143370471086 |
| Drain catch-up | drain_catchup_sec=40 |

## Interpretation

- Spool grew while drain was down; HTTP should stay green (fail-open / soft admission).
- Peak near `max_files` implies further profiles were dropped at admission (soft).
- After drain restart, queue should shrink (catch-up lag).
- Depth > 0 increases bytes per file vs shallow `busyWork` (same wall budget).

## Artifacts

- `k6.json`, `spool-timeseries.csv`, health + spool snapshots in this directory.
