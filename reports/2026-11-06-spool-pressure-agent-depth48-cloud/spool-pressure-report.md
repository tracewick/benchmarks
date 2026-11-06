# Report: spool pressure — 2026-11-06

Methodology: [METHOD.md](../../METHOD.md) layer B.

## Setup

| Field | Value |
| --- | --- |
| Host run dir | `/root/benchmarks/reports/_local/spool-pressure-20261106T235102Z` |
| Host | Linux nsk-1-vm-tsr3 7.0.0-42-generic #42-Ubuntu SMP PREEMPT_DYNAMIC Thu Oct 15 08:06:44 UTC 2026 x86_64 GNU/Linux |
| repo SHA | `e9c36a0fc007d73d5c5e392db328869350df5190` |
| sampleRate | `1.0` |
| TRACEWICK_SPOOL_MAX_FILES | `80` |
| WORK_STACK_DEPTH | 48 |
| Catch-up reader | `agent` |
| RATE / duration | 20 / 90s |
| Reader during load | **stopped** |

## Results

| Metric | Value |
| --- | --- |
| Peak spool files | 80 (cap 80) |
| Peak spool bytes | 174730 (0.17 MiB) |
| HTTP fail rate during fill | 0 |
| Achieved RPS | 19.790129113313295 |
| Drain catch-up | drain_catchup_sec=2
reader=agent |

## Interpretation

- Spool grew while drain was down; HTTP should stay green (fail-open / soft admission).
- Peak near `max_files` implies further profiles were dropped at admission (soft).
- After drain restart, queue should shrink (catch-up lag).
- Depth > 0 increases bytes per file vs shallow `busyWork` (same wall budget).

## Artifacts

- `k6.json`, `spool-timeseries.csv`, health + spool snapshots in this directory.
