# Report: soak 6h — 2026-11-07 (FPM × agent, depth-48)

Methodology: [METHOD.md](../METHOD.md). Limitations: [LIMITATIONS.md](../LIMITATIONS.md).

Raw artifacts: [2026-11-07-soak-fpm-agent-depth48-cloud/](./2026-11-07-soak-fpm-agent-depth48-cloud/).

## Results

| Service | RSS first → last | Δ | Verdict |
| --- | --- | --- | --- |
| app-fpm | 19.0 → 22.6 MiB | **+3.6 MiB** (+19%) | **stable** |
| app-agent | 8.0 → 10.7 MiB | **+2.7 MiB** (+33%) | **stable** |

k6: ~10 RPS, **0%** fail. Absolute growth small; agent % looks large only because of a tiny baseline.

## Pins

`RUNTIME=fpm`, `READER=agent`, `WORK_STACK_DEPTH=48`, `PHP_FPM_MAX_CHILDREN=8`, 10 RPS / 6h, sampleRate 0.1, 8 vCPU Timeweb.
