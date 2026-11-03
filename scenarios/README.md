# Scenarios

Named capacity profiles. Each Make target `bench-<name>` maps to one scenario and must follow [METHOD.md](../METHOD.md) (one factor per run).

| Name | Intent | Status |
| --- | --- | --- |
| `smoke` | Short clone → up → load → report path | Script stub (`generators/k6/smoke.js`); needs M1 app |
| `baseline` | Tracewick off / kill switch | Planned (M2) |
| `on` | Tracewick on at pinned `sampleRate` | Planned (M2) |
| `spool-pressure` | Queue growth / drain lag / drops | Planned (M3) |
| `chaos-pyroscope` | Latency / 5xx via Toxiproxy | Planned (M3) |
