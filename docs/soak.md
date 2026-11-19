# Observed 72-hour soak

Methodology: [METHOD.md](../METHOD.md). Limitations: [LIMITATIONS.md](../LIMITATIONS.md).

`make bench-soak` runs **baseline → warmup → steady → drain → cooldown**, with
one normal reader. Warmup must demonstrate successful delivery and drain before
steady load is allowed to start. Its default is one persistent RoadRunner worker, Go agent,
depth 48 and sample rate 0.1. No Grafana is started. FPM/drain and Swoole are also
selectable; RR uses exactly one worker so its diagnostics have a single owner.
The existing RR memory supervisor stays enabled at 256 MiB. A process identity
change invalidates continuity, including recycling within a running container.

The process probe buffers each record before publishing it. A transient healthcheck
that exits during collection is omitted. Missing or replaced service processes
still fail the identity check. Read failures for processes that remain present
abort collection with the PID and failed field in the error message.

This is sustained-load/resource-growth evidence, not a maximum-RPS test. Calibrate
RATE first on the actual host and hold it fixed afterwards. The short unprofiled
baseline is a sanity comparison, not a separate full overhead campaign. Record
CPU/RAM/OS, resource limits and competing work. Configure Docker proxy bypass for the local Pyroscope/network
when your Docker installation injects proxy environment variables. A 2 vCPU / 4 GiB host is a starting
configuration for a pilot, not a capacity guarantee.

## Requirements and exact pins

Use Linux, a local Docker Unix socket, Compose v2, Python 3, git, make and tmux.
Root or equivalent Docker access is needed for read-only `/proc` probes inside
the benchmark containers. No PHP, Go, k6 or Prometheus server is needed on the host.

Package and agent pins must be explicitly exported. This example pins the merged
17 November 2026 changes; select and review new SHAs deliberately for later runs:

```bash
export TRACEWICK_VERSION='dev-develop#55eb7bdb91cd4269a86bb0dd8ce22a243e5486b4'
export AGENT_REF=a15f0d310ba6d5942e67b37d3c3c55dc1b3b8100
export EXCIMER_VERSION=1.2.7
export EXCIMER_REF=23f541b9d970db0524a1b2506b4df727e5e59998
```

An exact published `TRACEWICK_VERSION=0.2.0` and `AGENT_VERSION=0.2.1` are also
supported (unset AGENT_REF to use a release). Those older releases do **not**
contain the current UoW/env changes. Floating constraints and branch-only core
pins are rejected. The PHP build argument now changes the actual Composer
constraint; it is not just an image label. Agent source builds verify the full
Git SHA. Before traffic, the runner compares installed package reference/version
and agent identity with the requested pins, then records image IDs, harness hashes/dirty status and runtime
versions in `identity.json`. The complete Composer lock is retained in the image.

EXCIMER_REF optionally builds the extension from an exact Git SHA and checks its
reported version against EXCIMER_VERSION. Without it the older PECL stand path
is preserved. Optional `proxy_ca` BuildKit secrets can provide a network CA for
Composer/Git source builds; this is not a request to disable TLS verification.

## Pilot, then 72 hours

Do not run `make up` alongside this scenario: the soak starts its own dedicated
Compose project `tracewick-soak` and uses the same default loopback ports. The
runner checks for an empty spool before starting its reader, and refuses an existing project or an occupied k6 REST endpoint. Use
SOAK_PROJECT and the port variables in compose.yaml for independent runs. The
scenario does not stop unrelated projects.

First check the harness on the target host:

```bash
make check-soak
BASELINE_DURATION=20s WARMUP_DURATION=20s DURATION=60s \
  COOLDOWN_DURATION=10s STATS_INTERVAL=5 TRACEWICK_SAMPLE_RATE=1 \
  SOAK_PROJECT=soak-pilot make bench-soak
```

Inspect `result.json`, reports and the resolved versions. A pilot is not long-soak
evidence. Stop the pilot project before reusing its ports:

```bash
docker compose -p soak-pilot --profile agent down
```

Then, after calibrating RATE (10 below is an example, not a universal target):

```bash
tmux new -s tracewick-soak
RATE=10 DURATION=72h BASELINE_DURATION=5m WARMUP_DURATION=5m \
  COOLDOWN_DURATION=2m DRAIN_TIMEOUT=2m STATS_INTERVAL=15 \
  TRACEWICK_SAMPLE_RATE=0.1 make bench-soak
```

Leave the session with Ctrl-b d; reattach with `tmux attach -t tracewick-soak`.
The script keeps benchmark containers for inspection after success or failure.
After preserving the evidence, stop only this project:

```bash
docker compose -p tracewick-soak --profile agent down
```

Do not remove volumes until the drain result and artifacts have been inspected.
The older Docker-stats-only runner remains `scripts/run-soak-legacy.sh` for
historical reproduction; its memory column is container memory, not process RSS.
Its reports cannot satisfy the new observed-soak criteria.

## What is collected

Every STATS_INTERVAL seconds, `telemetry.jsonl` records:

- Container identity/start time/restart count; cumulative cgroup CPU, throttling,
  memory usage, anonymous/file memory and resource limits for app/reader/Pyroscope,
  plus k6 while it runs. Container memory is never called RSS.
- Process PID/start ticks, RSS, anonymous memory, cumulative CPU, FD and OS-thread
  counts for app and reader. Root probes inspect only the container PID namespace and select PHP/RR/agent
  service processes, excluding transient runc/exec/healthcheck helpers.
- Actual spool pending files/bytes/age including claims and temporary files, plus
  rejected-file count; traversal fails above 100,000 entries instead of doing
  unbounded work or reporting an empty queue on errors.
- Agent queue/delivery/retry/reject metrics, and the single RR worker's profiler
  diagnostics. FPM/Swoole writer-drop totals are not available from this harness.
  Go goroutine/heap metrics are not currently exported; OS threads are not goroutines.
- k6 cumulative request, drop, error and latency checkpoints. The runner saves
  interval snapshots. k6 itself retains trend samples for end-of-phase quantiles,
  so track the generator's memory separately. REST includes cumulative p95 and
  the per-phase summary includes full-window p95 and p99.

`resource-series.csv` is a flattened export; `hourly.json` summarizes fixed-hour
CPU/request and memory observations. `result.json` and `soak-report.md` separate
validity from resource trends. RSS/anonymous slopes use the whole steady series;
first/last window averages and cumulative CPU per k6 HTTP request are also saved.
Process RSS sums count shared mappings per process. Container CPU includes observer
execs and health probes, so it is not pure profiler overhead. Baseline/warmup use
separate generator lifecycles; steady load uses one uninterrupted k6 process.

At the end of steady load the reader must empty the actual spool, including claims,
within DRAIN_TIMEOUT. Collection continues through cooldown. Sequential UoW should
create no new files after draining; continuous Swoole may still write idle process
profiles, which is recorded rather than treated as a sequential-worker failure.

DELIVERY_STALL_TIMEOUT defaults to 2m: old pending files or no agent delivery
progress with a nonempty queue abort the run during collection. Increasing
writer/delivery failure counters and rejected files also abort promptly.

Missing/malformed telemetry, counter resets, container/worker replacement, OOM,
large collection gaps, wrong pins or RoadRunner profiling settings, missed HTTP
checks, dropped or incomplete load iterations, absent delivery or increasing RR writer failures make
the observation invalid and the command exits nonzero. Raw artifacts and an invalid
report survive failures. A **valid observation** only means these validity checks
passed; inspect trends, queue and duration before deciding whether the soak passed.
Allow one iteration at either side of the scheduled count for the k6 deadline
boundary, while requiring zero reported drops.
RSS growth alone does not prove a leak: allocator retention and shared pages matter.

## Plots after collection

Optional plotting uses Matplotlib; it is not required during the load:

```bash
# Ubuntu, only if plots are wanted on this host:
sudo apt-get install python3-matplotlib
make plot-soak RUN_DIR=reports/_local/soak-<timestamp>
```

`resources.png` plots process RSS/anonymous memory, FD/threads, CPU per request and
pending files, with phase boundaries. Preserve JSONL/CSV/identity alongside plots.

Some managed Docker environments expose shared parent-cgroup statistics. The
collector rejects implausible lifetime CPU values. A local harness-only escape
hatch, SOAK_SMOKE_SHARED_CGROUP=1, permits **at most 60 seconds per phase**, labels
the result as a harness smoke and omits container CPU/request attribution. This
mode cannot produce a valid 72h observation and must not be used for capacity claims.
