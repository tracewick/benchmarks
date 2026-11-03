# Scenarios

Named capacity profiles. Each Make target `bench-<name>` maps to one scenario and must follow [METHOD.md](../METHOD.md) (one factor per run).

| Name | Intent | Status |
| --- | --- | --- |
| `smoke` | Short clone → up → load → report path; sampleRate `1.0` | `make bench-smoke` |
| `baseline` | Tracewick off / kill switch | Planned (M2) |
| `on` | Tracewick on at pinned `sampleRate` (0.1) | Planned (M2) |
| `spool-pressure` | Queue growth / drain lag / drops | Planned (M3) |
| `chaos-pyroscope` | Latency / 5xx via Toxiproxy | Planned (M3) |
