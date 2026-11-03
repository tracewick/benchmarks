# Scenarios

Named capacity profiles. Each Make target `bench-<name>` maps to one scenario and must follow [METHOD.md](../METHOD.md) (one factor per run).

| Name | Intent | Status |
| --- | --- | --- |
| `smoke` | Short clone → up → load → report path; sampleRate `1.0` | `make bench-smoke` |
| `overhead` | Fixed RPS: baseline (`TRACEWICK_ENABLED=0`) vs on (`sampleRate` 0.1) | `make bench-overhead` |
| `spool-pressure` | Queue growth / drain lag / drops | Planned (M3) |
| `chaos-pyroscope` | Latency / 5xx via Toxiproxy | Planned (M3) |
| `soak-72h` | Long RSS/CPU growth | Planned (after M2; upsize VPS first) |
