# Workload application (M1)

Placeholder for the PHP app under load:

- Tracewick via Packagist pin (`TRACEWICK_VERSION`, default `0.1.0`)
- SpoolSink → shared volume → `tracewick-drain` → Pyroscope
- HTTP surface for k6 (`BASE_URL`)

Do not vendor a copy of the library source here; depend on the published package or a pinned git ref and record it in every report.
