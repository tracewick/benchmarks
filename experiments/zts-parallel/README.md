# PHP ZTS / ext-parallel compatibility probe

Opt-in experiment: [methodology](../../METHOD.md), [limitations](../../LIMITATIONS.md),
[recorded results](../../reports/2026-11-19-zts-parallel.md).
This uses fixed-duration CLI work instead of k6 because it tests interpreter/thread isolation,
not HTTP capacity or application overhead. Nothing runs on the occupied soak server.

## Build and run

Requirements: Docker with named build contexts, Git, Python 3, a local core checkout with
Composer runtime dependencies installed, and Linux `/proc`. The image pins PHP 8.5.12 ZTS
by digest, Excimer 1.2.7 and parallel 1.2.15 by verified source commits. No PHP code is patched.

```bash
bash experiments/zts-parallel/build.sh
python3 experiments/zts-parallel/run.py \
  --core /absolute/path/to/tracewick --core-ref '<full-tested-commit>' \
  --output "$PWD/reports/_local/zts-parallel" --repeats 3
python3 -m unittest discover -s experiments/zts-parallel -p 'test_*.py' -v
```

Use an unchanged checkout and record its exact commit. The runner hashes `src/` before and
after the campaign. The recorded campaign used a `git archive` of the report's core revision
and its runtime `psr/log` 3.0.2 dependency. A version label alone is not source verification.

Each case gets a separate container, no network, a 2-CPU quota, 512 MiB memory and 128-PID
limit. Two case containers may run simultaneously on the shared host. A 20-second container
timeout escalates to KILL; a 30-second host watchdog also removes the named container.
Elapsed container startup/teardown time is retained for debugging, not an overhead result.

The recorded containers use the image's default root user and only disposable output mounts.
Spool directories/files are intentionally `0700`/`0600`; to export them without changing modes,
read the output mount from a container, for example:

```bash
docker run --rm --network none -v "$PWD/reports/_local/zts-parallel:/data:ro" \
  tracewick-zts-parallel:8.5 tar -czf - -C /data . > dataset.tar.gz
```

## Scenarios and checks

- Unprofiled control, native Excimer, UoW and Continuous: four worker interpreters and the
  parent execute distinct marker functions, wall and CPU modes, three repeats.
- Parent-only profiling checks that unprofiled worker stacks do not appear in the parent.
- One sleeping worker beside a busy worker distinguishes wall time from thread CPU time.
- UoW reuse: one profiler per runtime, 25 sequential tasks; no per-task profiler creation.
- Churn: 20 generations of four runtimes with native/UoW profilers; thread count after close.
- UoW shutdown: register shutdown delivery and leave profiling active until runtime close.

Checks require marker presence and absence of foreign markers, at least 50 ms of common work
overlap in concurrent cases, correct labels, no sampler/swallowed/drop/skip/failure diagnostics,
exact profile-to-decoded-spool weights, shutdown spool presence and no surviving worker threads
after churn. Sleeping CPU cases may correctly have zero events. Short reuse tasks may also be
empty; aggregate presence is checked, not a guarantee that every task receives a sample.
Native callbacks read an interpreter-local actor marker; OS TIDs are read outside callbacks.

`ProbeSink` writes real spool v2/compact-stacks and pprof outside the callback. The report's
dataset retains both, stdout/stderr and the complete numerical results. To check pprof files
after extracting the archive, use `go tool pprof -raw FILE.pprof`. Delivery to Pyroscope/agent
is not exercised here. Each runtime creates and owns its profiler; objects are never shared
between interpreters. The main matrix returns scalar JSON strings through Future.

## Standalone controls

These use the same image and a read-only mount of this experiment at `/probe`:

```bash
docker run --rm --network none -v "$PWD/experiments/zts-parallel:/probe:ro" \
  tracewick-zts-parallel:8.5 timeout --kill-after=2s 15s php /probe/minimal.php concurrent-trace

# Independent crash reproducer: only parallel is loaded, no core mount or Excimer.
docker run --rm --network none -v "$PWD/experiments/zts-parallel:/probe:ro" \
  tracewick-zts-parallel:8.5 timeout --kill-after=2s 15s \
  php -n -d extension=parallel.so /probe/literal-return.php array
# Change the last argument to json for the matched serialized-result control.
```

`literal-bootstrap.php` / `literal-return.php` reduce the initial probe crash to userland
fixtures and parallel. The array case is expected to exit 139 on the measured combination;
keep that failure as evidence, not a successful profiling result. JSON avoided this particular
reproducer; it is not a universal workaround or proof of the root C-level cause.

`edge.php MODE KIND` adds isolated active-profiler exception/kill checks. Supply the same
`/probe` and `/core` mounts plus a writable `/output`; MODE is `native` or `uow`, KIND is
`exception` or `kill`. A Channel barrier confirms sampling has started before kill. Use an
outer timeout as above. Kill does not promise profile delivery; normal exception cleanup uses
`finally`, and the runtime is then checked for reuse. The report records one run per edge case.

This is not an ASan/TSan run, long memory soak, production support declaration, cross-version
matrix, or test of forking with existing timers. Bootstrap/core sources must remain available
to every runtime. No automatic ZTS CI or production dependency is introduced.
