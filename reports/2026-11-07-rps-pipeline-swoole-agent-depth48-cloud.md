# Report: high-RPS pipeline — 2026-11-07 (Swoole × ContinuousProfiler × agent, depth-48)

Methodology: [METHOD.md](../METHOD.md). Limitations: [LIMITATIONS.md](../LIMITATIONS.md).

Raw artifacts: [2026-11-07-rps-pipeline-swoole-agent-depth48-cloud/](./2026-11-07-rps-pipeline-swoole-agent-depth48-cloud/).

## Results vs FPM×agent / RR×agent (same host / depth / ~700)

| Metric | Swoole × Continuous | RR × UoW | FPM × UoW |
| --- | --- | --- | --- |
| Achieved RPS | 697.50 | 697.55 | 697.58 |
| http_req_failed | 0% | 0% | 0% |
| Latency med / p95 / p99 | **42.1 / 73.2 / 97.1 ms** | 45.2 / 60.0 / 75.9 ms | 41.4 / 51.0 / 58.6 ms |
| Spool files max / last | **32 / 0** | 230 / 124 | 222 / 109 |

## Verdict

Swoole holds ~700 with agent. ContinuousProfiler aggregates into fewer spool files (10–15 s windows) than per-request UnitOfWork — max 32 files here, drained to 0 by end. Tail latency is a bit higher than FPM on this box; not a universal ranking.

## Pins

`RUNTIME=swoole`, `READER=agent`, `SWOOLE_WORKER_NUM=32`, `WORK_STACK_DEPTH=48`, 700 RPS / 5m, repo `c81d1d9`.
