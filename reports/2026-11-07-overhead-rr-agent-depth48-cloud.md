# Report: overhead A/B — 2026-11-07 (RoadRunner × agent, depth-48)

Methodology: [METHOD.md](../METHOD.md). Limitations: [LIMITATIONS.md](../LIMITATIONS.md).

Raw artifacts: [2026-11-07-overhead-rr-agent-depth48-cloud/](./2026-11-07-overhead-rr-agent-depth48-cloud/).

Same `/work` unit as FPM depth-48; runtime = **RoadRunner** (UnitOfWorkProfiler), reader = **go-agent 0.1.0**.

## Results

| Metric | baseline (off) | on (0.1) | delta |
| --- | --- | --- | --- |
| Latency med / p95 / p99 | 36.60 / 36.87 / 37.10 ms | 36.76 / 37.09 / 37.39 ms | **+0.16 / +0.23 / +0.28 ms** |
| HTTP fail | 0% | 0% | |
| app-rr CPU avg | 52.2% | 52.9% | **+0.7 pp** |

Vs FPM×agent depth-48 (~+0.5–1.7 ms): RR overhead is **similar or smaller** on this stand.

## Pins

`RUNTIME=rr`, `READER=agent`, `WORK_STACK_DEPTH=48`, `RR_NUM_WORKERS=4`, 20 RPS / 2m each arm, Packagist `0.1.0`, 8 vCPU Timeweb.
