# Scenarios

Named capacity profiles. Each Make target `bench-<name>` maps to one scenario and must follow [METHOD.md](../METHOD.md) (one factor per run).

| Name | Intent | Status |
| --- | --- | --- |
| `smoke` | Short clone → up → load → report path; sampleRate `1.0` | `make bench-smoke` |
| `overhead` | Fixed RPS: baseline (`TRACEWICK_ENABLED=0`) vs on (`sampleRate` 0.1); optional `WORK_STACK_DEPTH` | `make bench-overhead` |
| `spool-pressure` | Stop drain, fill toward `max_files`, catch-up lag; optional `WORK_STACK_DEPTH` | `make bench-spool-pressure` |
| `chaos-pyroscope` | Toxiproxy latency to Pyroscope; optional `WORK_STACK_DEPTH` | `make bench-chaos` |
| `soak` / `soak-72h` | Long RSS/CPU growth (FPM + drain series) | `make bench-soak` (default `RATE=10` `DURATION=72h`) |
| `rps-pipeline` | High-RPS hold + spool files/bytes; deeper stacks via `WORK_STACK_DEPTH` | `make bench-rps` (default `RATE=500` `DURATION=5m`, depth 48) |
