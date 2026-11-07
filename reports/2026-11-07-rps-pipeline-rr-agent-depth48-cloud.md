# Report: high-RPS pipeline — 2026-11-07 (RoadRunner × agent, depth-48)

Methodology: [METHOD.md](../METHOD.md). Limitations: [LIMITATIONS.md](../LIMITATIONS.md).

Raw artifacts: [2026-11-07-rps-pipeline-rr-agent-depth48-cloud/](./2026-11-07-rps-pipeline-rr-agent-depth48-cloud/).

## Results vs FPM×agent (same host / depth / ~700)

| Metric | RR × agent | FPM × agent |
| --- | --- | --- |
| Achieved RPS | 697.55 | 697.58 |
| http_req_failed | 0% | 0% |
| Latency med / p95 / p99 | **45.2 / 60.0 / 75.9 ms** | 41.4 / 51.0 / 58.6 ms |
| Spool files max / last | **230 / 124** | 222 / 109 |

## Verdict

RR holds the same ~700 target with agent (spool below soft `max_files`). Latency is a bit higher than FPM on this box; pipeline headroom looks comparable. FrankenPHP worker mode is the same profiler class — not a separate golden.

## Pins

`RUNTIME=rr`, `READER=agent`, `RR_NUM_WORKERS=32`, `WORK_STACK_DEPTH=48`, 700 RPS / 5m, repo `8d658ff`.
