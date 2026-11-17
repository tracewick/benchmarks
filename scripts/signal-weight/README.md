# Exact signal-weight probe

This is a short **correctness** probe under [METHOD.md](../../METHOD.md) layer C,
not the 5–15 minute k6 smoke, an overhead comparison, or a soak. It checks event
conservation, not statistical sampling accuracy or per-symbol CPU percentages.

Use sibling checkouts at `/workspace/tracewick`, `/workspace/agent`, and
`/workspace/benchmarks`, with dependencies installed for the PHP library. Record
their SHAs. Requires Docker, Go, Python 3, curl, and free localhost ports
4040, 4051, 8089, 9000. The PHP library and agent are read directly from those
checkouts; they are not silently replaced by published packages.

```bash
cd /workspace/benchmarks
# Optional for build networks with a proxy CA:
# export SIGNAL_PROXY_CA=/path/to/ca.pem
bash scripts/signal-weight/start.sh
```

The Dockerfile builds pinned Excimer source and copies RR 2025.1.15. PHP and
Pyroscope image tags are in the Dockerfile/start script; record image IDs and
versions for a run. RR client dependencies have their own checked-in lockfile.
Composer ignores platform constraints for this isolated harness because the
pipe relay does not use the optional sockets transport; the executed runtime is
verified separately. The main library dependencies are not changed.

`start.sh` starts named **disposable test containers**. It refuses name collisions;
inspect existing containers before choosing to remove them. It does not replace
the canonical capacity Compose stand. The standalone layout avoids an existing
Compose healthcheck parse error near line 77; that issue is not repaired here.

The FPM test pool runs with root workers (`-R`) so it can read restricted cloud
checkout directories. The agent and CLI probes also run as root in test
containers. This is solely a local synthetic-data test setup, **not** a deployment
example or UID/permissions validation. All ports bind to loopback. Output under
`/workspace/signal-verification/output` contains only synthetic profiles; the
harness makes those generated files readable/writable for inspection.

To rerun against already-running services:

```bash
python3 scripts/signal-weight/verify.py
# Independent reference decoder for captured agent pprof files:
go tool pprof -raw /workspace/signal-verification/output/push-<run>-0.pprof
```

Each run uses unique service names. Evidence is written under
`/workspace/signal-verification/output`, including JSONL capture manifests,
PHP pprof, raw agent pprof, Querier responses, and a summary. Preserve selected
artifacts in a report before deleting test containers or temporary directories.

## Assertions

- Ten sequential units for each runtime; 30 ms busy work, 1 ms wall sample period,
  sample rate 1.0; RR uses exactly one persistent worker and profiler instance.
- Stop the native sampler before reading `getLog()->getEventCount()` via
  reflection, then call UoW stop/flush. This freezes the independent oracle.
- Native event sum = collected profile weights = decoded compact spool weights.
- Ten spool files are encoded with the PHP pprof encoder and drained by a real
  agent. A forwarding HTTP proxy extracts the actual pprof sent by the agent;
  it forwards the unmodified push to real Pyroscope and propagates its status.
- PHP pprof sum = actual agent pprof sum = native events × 1,000,000 ns.
- Pyroscope Querier total equals that value exactly and contains `signalWork`.
- Successful agent delivery acknowledges the spool; no `.spool` files remain.

`maxSamples=100000` deliberately avoids threshold flushes during these short
units, directly exercising the explicit-flush bug. This does not replace the
library's real-Excimer automatic-segment/rotation tests. It does not validate
spans, auth, retry/duplicate handling, chaos, concurrent profiling, or all caps.
Native scheduling can produce fewer than 30 events per request; equality is to
the observed native event count, not an assumed wall-clock sample count.

Cleanup after saving evidence:

```bash
docker stop -t 2 signal-rr signal-fpm signal-pyroscope
docker rm signal-rr signal-fpm signal-pyroscope
```
