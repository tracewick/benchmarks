# Report: high-RPS pipeline — 2026-11-06 (agent, depth-48)

Methodology: [METHOD.md](../METHOD.md). Limitations: [LIMITATIONS.md](../LIMITATIONS.md).

Raw artifacts: [2026-11-06-rps-pipeline-agent-depth48-cloud/](./2026-11-06-rps-pipeline-agent-depth48-cloud/).

Same hold as [drain ~700](./2026-11-06-rps-pipeline-cloud.md); reader = **go-agent 0.1.0**.

## Identity

| Field | Value |
| --- | --- |
| Date (UTC) | 2026-11-06T23:57:45Z |
| This repo SHA | `e9c36a0fc007d73d5c5e392db328869350df5190` |
| Host | Timeweb `nsk-1-vm-tsr3` **8 vCPU** |
| Make target | `READER=agent make bench-rps` |

## Pins

| Component | Value |
| --- | --- |
| RATE / DURATION | 700 req/s / 5m |
| sampleRate | 0.1 |
| WORK_STACK_DEPTH | 48 |
| PHP_FPM_MAX_CHILDREN | 32 |
| READER | **agent** 0.1.0 |

## Results vs drain (same host / depth)

| Metric | agent | drain (canonical) |
| --- | --- | --- |
| Achieved RPS | 697.58 | 697.57 |
| http_req_failed | 0% | 0% |
| Latency med / p95 / p99 | 41.4 / 51.0 / 58.6 ms | 41.3 / 51.0 / 58.1 ms |
| Spool files max / last | **222 / 109** | **602 / 600** |
| Spool bytes max / last | **0.57 / 0.23 MiB** | **1.09 / 1.09 MiB** |

## Verdict

HTTP path identical. Agent keeps spool **well below** soft `max_files=500` at the same ~700 RPS where PHP drain sat at soft admission (~600 files). Matches the expectation that go-agent raises pipeline headroom.
