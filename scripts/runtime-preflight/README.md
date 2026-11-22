# Development runtime preflight

Follow [METHOD.md](../../METHOD.md). This campaign evaluates pinned development
sources before a published RC exists. It creates no release tags.

## Inputs

- Core develop edb24275b48b6145216e8f8af34304819adf64f1.
- Agent develop d464fac4a69a57b36dd171841012e69f3f5536ed.
- Symfony bundle develop 7928d3e69e480603442088ae2d4786d9a7ebccf1.
- Excimer 1.2.7 at 23f541b9d970db0524a1b2506b4df727e5e59998.
- Platform images selected by pinned-build.py, matching the PHP 8.4.27 soak.
- k6 1.8.2 and Pyroscope 2.4.2 use the same concrete digests as that soak.
- One RR worker, depth 48, 25 ms busy work plus 10 ms sleep, 10 arrivals/s,
  sample rate 0.1. One Go reader. No concurrent workload during A/B measurements.

Export the regular observed-soak pin variables and dedicated SOAK_PROJECT,
REPORTS_DIR and host ports. Generate a Compose build override with
python3 scripts/runtime-preflight/pinned-build.py followed by its output directory,
then use both compose.yaml and the generated compose-build.json.
Build app-rr and app-agent before measurement. Retain the generated Dockerfiles
and platform-pins.json with the evidence.

## Overhead

Run python3 scripts/runtime-preflight/overhead.py for off/on, on/off, off/on.
Every measurement starts with a fresh app worker, two minutes of equal-state
settling and ten minutes of measured load. Backend and reader persist between
phases and each phase drains before the next starts. All six phases use the same
strict k6 workload and observation interval.

The runner verifies installed references, real Excimer, active settings, worker
continuity, zero writer failures, zero load failures/drops and successful drain.
Compare process CPU/request and per-phase latency across the three pairs. Preserve
every repeat, including failures. Report the spread alongside a typical delta.
The --smoke option uses two phases, 15 seconds settling and 30 seconds measurement.
Use STATS_INTERVAL=5 and PREFLIGHT_IMAGE_TAG to reuse prepared images in its
own SOAK_PROJECT. A smoke validates wiring only.

## Recovery

Run python3 scripts/runtime-preflight/recovery.py on the prepared project
after overhead. It recreates app and reader, then holds one 35-minute generator.

| Elapsed time | Action |
| --- | --- |
| 0–5 min | Healthy reference |
| 5 min | Stop Pyroscope |
| 10 min | Start Pyroscope and observe recovery |
| 15 min | Gracefully stop reader |
| 16 min | Start reader |
| 20 min | Pause backend, establish inflight upload, kill reader and record orphaned claims |
| 21 min | Resume backend and start reader |
| Until 35 min | Observe delivery and default stale-claim recovery |
| After load | Require complete drain within 12 min |

The reader's automatic restart policy is disabled for this explicit fault schedule.
There is exactly one reader. Default ten-minute stale-claim age is retained.
Expected delivery retries are recorded. Writer failures, rejected work, invalid
load, telemetry failures and unexpected app/reader replacements fail the case.
An intentionally restarted reader begins a new identity/counter epoch. App
continuity remains mandatory across every injected fault. Epoch counters cannot
be treated as a single uninterrupted counter.

## Symfony

Symfony.Dockerfile builds the original bundle develop snapshot with real
Excimer and Symfony 7.4 dependencies. The root test project's core requirement is
explicitly pinned to current develop so runtime source behavior can be exercised.
The original package snapshot is retained at /sources/bundle.

install-probe.php evaluates original package metadata independently. The path
repository names current core 1.0.0-dev for a source compatibility check, without
creating or claiming a published RC. Preserve Composer's actual exit code and
report dependency-resolution failures separately from runtime outcomes.

The production runtime autoloader excludes dev-only Messenger polyfills.
Run the existing PHPUnit suite with dev autoload enabled in a separate
test container. Use UID:GID 33:33 for application and reader.

Run symfony.php with check, http 1200 and messenger 1200 in fresh containers.
The check uses sample rate 1 to verify main requests, subrequests, exceptions,
console exit codes, queued handling, message exceptions and profiler reuse.
Inspect emitted spool labels before starting the single reader.
Sustained HTTP and Messenger cases use 0.1. Their intended application/handler
exceptions are counted explicitly. They use a real FrameworkBundle and Messenger
consume command with an in-memory transport. They establish integration behavior
for this fixture. Broker transport durability is outside this experiment.
