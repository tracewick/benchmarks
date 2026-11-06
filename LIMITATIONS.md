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
- **Canonical** capacity goldens for overhead / spool pressure / chaos / high-RPS use `WORK_STACK_DEPTH=48` on the 8 vCPU stand (same wall budget as shallow; larger profiles). Nov-3 depth-`0` reports on 2 vCPU are **historical** only — useful to see how depth multiplies spool bytes; do not cite them as current overhead/pipeline numbers, and do not mix host-size + depth into one “delta”.
- High-RPS figures are **single-instance** (one VPS: app + drain + Pyroscope + k6 on the same host unless a report says otherwise). A sustained RPS number is the **ceiling of that host + work unit + FPM pool**, not a universal Tracewick SLO and not multi-node “prod highload”. The checked-in ~700 RPS hold used PHP `tracewick-drain`; spool sitting above soft `max_files` under that reader is soft admission, not a hard-cap bug. go-agent is expected to raise pipeline headroom on the same stand.
- The checked-in **72h soak** remains shallow-payload evidence until a depth-48 soak exists.
- Layer C checks order-of-magnitude signal only; flame-graph symbol share is not a contractual metric in v1.

## Comparisons

- No marketing bake-off against Arc Lamp, Excimetry, or eBPF agents in v1.
- Multi-region / Kubernetes operator workloads are out of scope for the first stand.

## Operations

- Secrets never belong in git; use `.env` from `.env.example`.
- Toxiproxy chaos scenarios are optional and documented when enabled; default smoke does not require them.
