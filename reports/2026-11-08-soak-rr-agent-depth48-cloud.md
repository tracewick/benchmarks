# Report: soak 6h — 2026-11-08 (RoadRunner × agent, depth-48)

Methodology: [METHOD.md](../METHOD.md). Limitations: [LIMITATIONS.md](../LIMITATIONS.md).

Raw artifacts: [2026-11-08-soak-rr-agent-depth48-cloud/](./2026-11-08-soak-rr-agent-depth48-cloud/).

Remake after fixing the stand: one `UnitOfWorkProfiler` per RR worker (not `::create()` per request). Earlier leaky run (~+1 GiB / 6h) is not checked in.

## Results

| Service | RSS first → last | Δ | Verdict |
| --- | --- | --- | --- |
| app-rr | 95.2 → 98.6 MiB | **+3.4 MiB** (+3.5%) | **stable** |
| app-agent | 15.4 → 17.8 MiB | **+2.4 MiB** (+15%) | **stable** |

k6: ~10 RPS, **0%** fail. Matches FPM/Swoole agent soaks on this host.

## Pins

`RUNTIME=rr`, `READER=agent`, `WORK_STACK_DEPTH=48`, `RR_NUM_WORKERS=8`, 10 RPS / 6h, sampleRate 0.1, repo `8f7e372`.
