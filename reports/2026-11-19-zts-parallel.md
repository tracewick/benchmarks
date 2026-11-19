# PHP ZTS / ext-parallel: Excimer and Tracewick — 2026-11-19

Methodology: [METHOD.md](../METHOD.md). Limitations: [LIMITATIONS.md](../LIMITATIONS.md).
Reproduction: [experiment](../experiments/zts-parallel/README.md).

**Verdict:** the 66-case profiling matrix passes when each interpreter creates its own profiler
and returns JSON messages. A separate reduced array-result case segfaults 3/3 with only
parallel loaded: neither Excimer nor Tracewick is present in that reproducer. This is useful
compatibility evidence with a concrete runtime caveat, not an unconditional ZTS support claim.

## Identity and pins

| Component | Tested identity |
| --- | --- |
| Date | 2026-11-19 UTC |
| Entry point | `python3 experiments/zts-parallel/run.py` (opt-in CLI experiment, no Make/HTTP target) |
| Benchmarks base | `934791c` on main; probe sources and data are in this report's PR |
| Host | Managed shared Linux 6.18.57 x86_64, 3 visible CPUs, Intel Xeon Platinum 8573C, approximately 9.7 GiB visible RAM |
| Isolation | Each matrix case: 2-CPU quota, 512 MiB RAM, 128 PIDs, no network; two case containers at a time |
| PHP | 8.5.12 ZTS; CLI OPcache disabled |
| Base image | `php:8.5.12-zts-bookworm@sha256:c6a2606c831a21992c2cdd0ae5a4e87af02348c4c3f66621bfb8b87702977ee3` |
| Excimer | 1.2.7, `23f541b9d970db0524a1b2506b4df727e5e59998` |
| parallel | 1.2.15, `f62fab1225f687de60d789002c9b49467d3e04de` |
| Built image | `sha256:926dd4b694f2c234ef8bb0942984cb65fb8bbf33bff8f63ed5b173e4ae7d0ae8` |
| Core | `edb24275b48b6145216e8f8af34304819adf64f1`, exact Git export; runtime dependency psr/log 3.0.2 |
| Core source fingerprint | `659c386ea0e455802e7c95f025518022f9df95d70fae5921934163971a8015e9`; unchanged before/after |
| Sampling | 1 ms wall/CPU period, native flush threshold 16, depth 128 native / 256 Tracewick; UoW sampleRate 1.0 |
| Workload | Synthetic marker functions, usually 300 ms; 30 ms tasks in reuse/churn; three repeats per matrix case |
| Delivery | Real spool v2/compact-stacks and pprof; no agent/PHP drain/Pyroscope in this experiment |

Fixed-duration CLI work replaces k6 to isolate interpreter/thread semantics. No HTTP throughput,
latency or NTS-versus-ZTS overhead is inferred. Container elapsed times include launch/teardown.

## Profiling matrix

| Scenario | Modes / event types | Runs | Result |
| --- | --- | ---: | --- |
| Four workers plus parent, at least 50 ms common work overlap | off/native/UoW/Continuous × wall/CPU | 24 | Pass |
| Parent profiled; four workers unprofiled | native/UoW × wall/CPU | 12 | Pass; no worker markers in parent |
| Sleeping worker alongside busy worker | native/UoW × wall/CPU | 12 | Pass; CPU isolation below |
| Same runtime/profiler, 25 sequential tasks per worker | UoW × wall/CPU | 6 | Pass; short empty profiles noted below |
| 20 generations of four runtimes | native/UoW × wall | 6 | Pass; thread count returns to 1 after each generation |
| Leave UoW active, close runtime, flush on shutdown | UoW × wall/CPU | 6 | Pass; all four workers write their final spool |

Every profiled actor has its own marker and no other actor's marker in its observed stacks.
Native callbacks report the expected interpreter-local actor. Tracewick profile labels and
decoded spool labels remain attached to their actor. No sampler failures, swallowed errors,
drops, skips or rejects were reported. OS TIDs are recorded outside callbacks.

The native sleeping worker records 300–302 wall periods and **0 CPU periods**, while its busy
sibling records 285–296 CPU periods. UoW records 300–301 wall periods and **0 CPU periods** in
the sleeper, versus 282–293 CPU periods in the busy sibling. Counts are weighted timer periods,
not independent statistical trials or a CPU-percentage accuracy certificate.

There are **928 spool files / 42,737 weighted periods**, exactly matching the captured profiles.
All **928 pprof files** parse with Go 1.27.4 `go tool pprof -raw`. This checks encoding and
profile-to-spool conservation, not an independent native-to-profile weight oracle.

Of 600 short reuse tasks, 11 produced empty profiles (3 wall, 8 CPU); they are retained in the
diagnostics. Three sleeping-CPU UoW cases also correctly had empty profiles. No claim is made
that every short unit receives a sample. Parent-profiled cases retain a main timer thread
(`Threads=2`) until interpreter shutdown; worker-only churn returns to 1 after each close.
Thread counts are not RSS trends or a memory-leak test.

## Lifecycle edge checks

Four additional isolated wall-mode cases, one observation each: native/UoW × exception/kill.
A Channel confirms profiling started before forced kill. Exceptions are cleaned up in `finally`,
and the same runtime subsequently executes another task. Kill raises the expected killed-future
error. All four processes exit normally and return to one thread; no timeout or native warning
was observed. These checks do not promise profile delivery on kill or prove long-run cancellation safety.

## Independent array-result crash

The initial richer probe exited 139 even with profiling disabled. Reducing it exposed a
reproducer using only PHP and parallel: a bootstrap-defined userland fixture returns an array
containing a literal string, the parent retrieves results, closes runtimes, then encodes results.
See `literal-bootstrap.php` / `literal-return.php` in the experiment directory.

| Matched reduced control | Loaded extensions | Repeats | Exit |
| --- | --- | ---: | --- |
| Return arrays through Future | parallel only (`php -n -d extension=parallel.so`) | 3 | 139 / 139 / 139 |
| Encode in worker, return JSON string | parallel only | 3 | 0 / 0 / 0 |

There is no core autoloader, profiler, timer or Excimer extension in this reduced case.
It establishes a crash in the measured PHP/parallel combination, not which upstream C component
owns the bug. It does not mean all arrays fail: the main runner's six simpler unprofiled
array/JSON controls without Excimer all pass. The native-only minimal profiler controls also pass.
No extension/library patch, upstream issue or outreach was made. JSON avoids this reproducer;
it is not a general thread-safety guarantee. Sanitizer/debug builds and other PHP/parallel versions
remain follow-up investigation.

## Evidence and scope

[Summary](2026-11-19-zts-parallel/summary.json),
[full results (gzip)](2026-11-19-zts-parallel/results.json.gz),
[raw spool/pprof/stdout/stderr archive](2026-11-19-zts-parallel/artifacts.tar.gz),
[crash controls](2026-11-19-zts-parallel/literal-controls-final.json),
[edge results](2026-11-19-zts-parallel/edge-results.json),
[native controls](2026-11-19-zts-parallel/native-controls.json),
[pprof validation](2026-11-19-zts-parallel/pprof-validation.json),
[SHA-256 checksums](2026-11-19-zts-parallel/checksums.txt).

This is one pinned Linux/PHP/extension combination, synthetic work and short runs. The matrix
constructs profilers inside each runtime, reuses them for sequential work and exchanges scalar
JSON data; it does not share profiler/sink/native objects across threads. No long RSS/CPU soak,
race sanitizer, backend delivery, production application, cross-version or platform matrix,
or forking with active native timers was tested. The occupied 72h soak VPS was not used or changed.
This experiment neither changes runtime support policy nor closes the RC soak/overhead gates.
