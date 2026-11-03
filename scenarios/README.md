# Scenarios

Named capacity profiles. Each Make target `bench-<name>` maps to one scenario and must follow [METHOD.md](../METHOD.md) (one factor per run).

| Name | Intent | Status |
| --- | --- | --- |
| `smoke` | Short clone → up → load → report path; sampleRate `1.0` | `make bench-smoke` |
| `overhead` | Fixed RPS: baseline (`TRACEWICK_ENABLED=0`) vs on (`sampleRate` 0.1) | `make bench-overhead` |
| `spool-pressure` | Stop drain, fill toward `max_files`, catch-up lag | `make bench-spool-pressure` |
| `chaos-pyroscope` | Toxiproxy latency to Pyroscope | `make bench-chaos` |
| `soak-72h` | Long RSS/CPU growth | Planned (after M2; upsize VPS first) |
