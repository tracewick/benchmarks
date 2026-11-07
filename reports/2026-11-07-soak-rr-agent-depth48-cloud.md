# Report: soak 6h — 2026-11-07 (RoadRunner × agent, depth-48)

Methodology: [METHOD.md](../METHOD.md). Limitations: [LIMITATIONS.md](../LIMITATIONS.md).

Raw artifacts: [2026-11-07-soak-rr-agent-depth48-cloud/](./2026-11-07-soak-rr-agent-depth48-cloud/).

## Results

| Service | RSS first → last | Δ | Verdict |
| --- | --- | --- | --- |
| app-rr | 208 → 1189 MiB | **+981 MiB** (+472%) | **growth concern** |
| app-agent | 11.5 → 10.1 MiB | **−1.4 MiB** | **stable** |

k6: ~10 RPS, **0%** fail for the full 6h. go-agent does **not** leak here. RoadRunner / UnitOfWorkProfiler path under depth-48 needs a follow-up (RSS climbed ~1 GiB; late `Cannot fork` on Docker healthcheck while `/health` still answered).

## Pins

`RUNTIME=rr`, `READER=agent`, `WORK_STACK_DEPTH=48`, `RR_NUM_WORKERS=8`, 10 RPS / 6h, sampleRate 0.1.
