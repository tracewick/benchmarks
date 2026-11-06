# Limitations

What this repository does **not** claim. Aligns with [METHOD.md](METHOD.md) non-goals and the library's honesty policy.

## Scope

- **Not** a substitute for `tracewick/tracewick` CI (unit, integration, Infection, chaos wiring).
- **Not** a product UI or hosted SaaS for profiling.
- Library docker stand (`make stand-up` / `app-up`) remains for correctness; capacity campaigns live **here**.

## Numbers

- Results are tied to a pinned host class, image tags, and scenario parameters. They are not universal SLOs.
- Smoke windows (minutes) are not soak proof (hours/days).
- The checked-in **72h soak** covers **PHP-FPM** (`pm=static` long-lived workers) with **`UnitOfWorkProfiler` + SpoolSink + drain** only. It is not evidence for RoadRunner, `ContinuousProfiler`, or go-agent — those need separate soaks.
- High-RPS runs may set `WORK_STACK_DEPTH>0` for larger spool payloads; golden smoke/overhead/soak keep depth `0` so their timings stay comparable.
- Layer C checks order-of-magnitude signal only; flame-graph symbol share is not a contractual metric in v1.

## Comparisons

- No marketing bake-off against Arc Lamp, Excimetry, or eBPF agents in v1.
- Multi-region / Kubernetes operator workloads are out of scope for the first stand.

## Operations

- Secrets never belong in git; use `.env` from `.env.example`.
- Toxiproxy chaos scenarios are optional and documented when enabled; default smoke does not require them.
