# Report: chaos Pyroscope latency — 2026-11-06 (agent, depth-48)

Methodology: [METHOD.md](../METHOD.md) layer B. Limitations: [LIMITATIONS.md](../LIMITATIONS.md).

Raw artifacts: [2026-11-06-chaos-pyroscope-agent-depth48-cloud/](./2026-11-06-chaos-pyroscope-agent-depth48-cloud/).

Same toxic as [drain depth-48](./2026-11-06-chaos-pyroscope-depth48-cloud.md); reader = **go-agent 0.1.0**.

## Setup

| Field | Value |
| --- | --- |
| Host | Timeweb `nsk-1-vm-tsr3` (**8 vCPU**) |
| repo SHA | `e9c36a0fc007d73d5c5e392db328869350df5190` |
| Toxic | Toxiproxy **3000 ms** latency drain/agent → Pyroscope |
| sampleRate | `1.0` |
| WORK_STACK_DEPTH | **48** |
| READER | **agent** |
| RATE / duration | 20 req/s / 60s |

## Results vs drain

| Metric | agent | drain (depth-48 ref) |
| --- | --- | --- |
| Peak spool files | **172** | **500** (hit soft ceiling) |
| Peak spool bytes | ~0.51 MiB | ~1.03 MiB |
| HTTP fail rate | **0%** | 0% |

## Verdict

App stayed green. Under the same 3s toxic, agent backlog stayed far below soft `max_files` while PHP drain filled to 500. (Auth/404 **pause** behaviour of the agent was not exercised here — latency toxic only.)
