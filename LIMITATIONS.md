# Limitations

What this repository does **not** claim. Aligns with [METHOD.md](METHOD.md) non-goals and the library's honesty policy.

## Scope

- **Not** a substitute for `tracewick/tracewick` CI (unit, integration, Infection, chaos wiring).
- **Not** a product UI or hosted SaaS for profiling.
- Library docker stand (`make stand-up` / `app-up`) remains for correctness; capacity campaigns live **here**.

## Numbers

- Results are tied to a pinned host class, image tags, and scenario parameters. They are not universal SLOs.
- Smoke windows (minutes) are not soak proof (hours/days).
- Short **6h soaks** (depth-48, `READER=agent`) cover **FPM**, **RoadRunner**, and **Swoole** (all stable with go-agent). An earlier RR stand bug (per-request `UnitOfWorkProfiler::create()` in long-lived workers) grew RSS ~+1 GiB / 6h — fixed by constructing the profiler once per worker; that leaky run is not a golden. The older **72h** report is FPM + drain + shallow stacks only.
- **Canonical** capacity goldens for overhead / spool pressure / chaos / high-RPS use `WORK_STACK_DEPTH=48` on the 8 vCPU stand (same wall budget as shallow; larger profiles). Nov-3 depth-`0` reports on 2 vCPU are **historical** only — useful to see how depth multiplies spool bytes; do not cite them as current overhead/pipeline numbers, and do not mix host-size + depth into one “delta”.
- High-RPS figures are **single-instance** (one VPS: app + reader + Pyroscope + k6 on the same host unless a report says otherwise). A sustained RPS number is the **ceiling of that host + work unit + FPM pool**, not a universal Tracewick SLO and not multi-node “prod highload”. With PHP `tracewick-drain` at ~700 RPS, spool sat at soft admission (~600 files). With go-agent `0.1.0` on the same hold, spool stayed below soft `max_files` (~222 peak / ~109 last) — reader choice matters for pipeline headroom. Soft overshoot past `max_files` is fail-open by design, not a hard-cap bug.
- Depth-48 soak evidence for FPM/RR/Swoole×agent is checked in; 72h shallow FPM+drain remains historical.
- Capacity layer C checks order-of-magnitude signal. A separate [controlled function-share experiment](reports/2026-11-18-profile-shares.md) compares selected wall-time workloads with independent elapsed-time measurements; flame-graph symbol share is not a universal or contractual metric in v1.

## Explicit-flush weight correction

The [2026-11-17 signal-weight report](reports/2026-11-17-signal-weights.md) verifies
exact native-event conservation on the merged fix for short CLI/FPM/RR units.
Earlier reports remain evidence about their pinned versions. Explicit-flush
weights could be inflated; the effect depends on threshold versus explicit
flushes and cannot be corrected with one universal multiplier. Revalidate signal
weights and remeasure overhead before presenting historical observations as
current-version claims. This short probe does not establish sampling accuracy,
capacity, or 72h stability.

## Experimental ZTS compatibility

The [PHP ZTS/ext-parallel experiment](reports/2026-11-19-zts-parallel.md) covers one pinned
Linux/PHP/extension combination. Its profiling matrix uses JSON result messages, and a separate
array-result control crashes without either Excimer or Tracewick loaded. Passing profile
isolation checks does not establish general thread safety, long-term memory stability or
support for arbitrary objects crossing runtimes. No NTS/ZTS overhead comparison was measured.

## Comparisons

- No marketing bake-off against Arc Lamp, Excimetry, or eBPF agents in v1.
- Multi-region / Kubernetes operator workloads are out of scope for the first stand.

## Operations

- Secrets never belong in git; use `.env` from `.env.example`.
- Toxiproxy chaos scenarios are optional and documented when enabled; default smoke does not require them.

## Observed-soak instrumentation

The new [soak runner](docs/soak.md) separates process RSS from cgroup memory and
checks worker/container continuity. Historical Docker-stats CSVs do not provide
per-process RSS, FD, thread, queue or restart evidence. Current instrumentation
does not retroactively close the 72h depth-48 gate. Shared-cgroup managed runners
can test the harness only; resource attribution must be validated on the actual
Linux benchmark server. k6 REST quantiles are cumulative, not hourly quantiles;
Go goroutine/heap and FPM/Swoole writer-drop totals are not collected.
