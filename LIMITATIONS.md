# Limitations

What this repository does **not** claim. Aligns with [METHOD.md](METHOD.md) non-goals and the library's honesty policy.

## Scope

- **Not** a substitute for `tracewick/tracewick` CI (unit, integration, Infection, chaos wiring).
- **Not** a product UI or hosted SaaS for profiling.
- Library docker stand (`make stand-up` / `app-up`) remains for correctness; capacity campaigns live **here**.

## Numbers

- Results are tied to a pinned host class, image tags, and scenario parameters. They are not universal SLOs.
- Smoke windows (minutes) are not soak proof (hours/days).
- Short **6h soaks** (depth-48, `READER=agent`) cover FPM, RoadRunner, and Swoole: FPM/Swoole/agent look stable; **RoadRunner showed ~+1 GiB RSS growth** under the same load — treat RR long-lived memory as an open follow-up, not a green soak. The older **72h** report is FPM + drain + shallow stacks only.
- **Canonical** capacity goldens for overhead / spool pressure / chaos / high-RPS use `WORK_STACK_DEPTH=48` on the 8 vCPU stand (same wall budget as shallow; larger profiles). Nov-3 depth-`0` reports on 2 vCPU are **historical** only — useful to see how depth multiplies spool bytes; do not cite them as current overhead/pipeline numbers, and do not mix host-size + depth into one “delta”.
- High-RPS figures are **single-instance** (one VPS: app + reader + Pyroscope + k6 on the same host unless a report says otherwise). A sustained RPS number is the **ceiling of that host + work unit + FPM pool**, not a universal Tracewick SLO and not multi-node “prod highload”. With PHP `tracewick-drain` at ~700 RPS, spool sat at soft admission (~600 files). With go-agent `0.1.0` on the same hold, spool stayed below soft `max_files` (~222 peak / ~109 last) — reader choice matters for pipeline headroom. Soft overshoot past `max_files` is fail-open by design, not a hard-cap bug.
- Depth-48 soak evidence is the 6h agent matrix above; the 72h shallow FPM+drain report remains historical.
- Layer C checks order-of-magnitude signal only; flame-graph symbol share is not a contractual metric in v1.

## Comparisons

- No marketing bake-off against Arc Lamp, Excimetry, or eBPF agents in v1.
- Multi-region / Kubernetes operator workloads are out of scope for the first stand.

## Operations

- Secrets never belong in git; use `.env` from `.env.example`.
- Toxiproxy chaos scenarios are optional and documented when enabled; default smoke does not require them.
