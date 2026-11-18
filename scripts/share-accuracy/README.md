# Known-function wall-time shares

Method: [METHOD.md](../../METHOD.md), signal layer C. This is a controlled accuracy experiment,
not an overhead comparison, capacity test, long soak or universal profiler accuracy guarantee.
The earlier exact-weight campaign is separate and is not repeated here.

## Run

Use sibling checkouts at `/workspace/tracewick`, `/workspace/agent` and `/workspace/benchmarks`.
Install the core's Composer dependencies. Core/agent source trees must be clean. Requires Python
3.12+, Go, Docker and a PHP CLI image with Excimer 1.2.7. Build the normal core stand PHP image
with `make -C ../tracewick stand-build PHP_VERSION=8.5` (no services need to be started), then:

```bash
make bench-share-accuracy
# Or explicitly select prepared images and an unused loopback port:
python3 scripts/share-accuracy/run.py --php-image tracewick-php:8.5 \
    --pyroscope-image grafana/pyroscope:2.4.3 --port 14040
```

The runner builds the current Go agent, records revisions/image IDs and its input file hashes,
starts its own fresh Pyroscope container, then executes the serial matrix. It refuses an occupied
port and removes only its own container on completion/failure. Do not run it on a host whose soak
is in progress. It does not operate the canonical Compose stand or contact the benchmark VPS.
Local evidence is under `reports/_local/share-<UTC>/`; preserve a selected **complete** run in a
report before removing scratch output. Never publish the built agent binary or unrelated files.

## Fixed matrix and acceptance

Three workloads, two periods and three deterministic repetitions give **18 predeclared runs**:

| Workload | Requested alpha/beta time | Beta implementation |
| --- | --- | --- |
| busy-70 | 70/30 | PHP loop |
| busy-20 | 20/80 | PHP loop |
| mixed-70 | 70/30 | `usleep` |

- CLI sequential UoW, `sampleRate=1.0`, wall event, default depth 256, native flush threshold 1000.
- Periods: 10 ms (100 Hz), 1 ms (1000 Hz).
- Warm up both functions before sampling; then at least 40 seconds/run at 100 Hz and 12 seconds
  at 1000 Hz. At least 3000/9000 weighted classified sampling periods, respectively.
- Deterministic seeds and a shuffled case order are saved before work starts. Every cycle has a
  jittered total duration between 20 and 80 ms and randomized alpha/beta order to reduce phase
  locking. Each repetition starts a fresh PHP process.
- The oracle sums `hrtime()` elapsed intervals around `shareAlpha` and `shareBeta` calls. Nominal
  requested proportions are **not** the expected result: timer rounding, descheduling, callback
  time and `usleep` overshoot belong to the actual elapsed-time reference.
- A real Go-agent drains the resulting spool to Pyroscope. The checker reads a unique service's
  actual `SelectMergeStacktraces` flamegraph; it does not substitute source-profile counts.
- Use **inclusive** weights below each mutually exclusive phase marker. Child frames (including
  Excimer's callbacks and the called C function) belong to the enclosing phase, so leaf self
  weights alone are not the quantity being compared.
- Each phase's absolute error must be **<=5 percentage points** relative to the independently
  measured alpha/beta elapsed-time split. Weight outside the two markers must be **<=1%** of the
  backend total, preventing normalization from hiding missing attribution. Boundary comparisons
  use integer cross-products to avoid floating-point rounding changing acceptance.
- Weighted periods are weight/period, **not independent Bernoulli observations**. No binomial
  confidence interval or statistical-independence claim is made. Repetitions expose variability;
  every individual run must pass, not just an average or selected seed.
- The swapped-symbol negative control preserves the total weight but must fail the share bound
  for every run. Unit tests also cover hidden unclassified weight, small volume, exact thresholds,
  malformed graphs and missing/overlapping markers.

The source sink records per-phase counts only for diagnostics; it never defines the oracle.
Normal UoW stop/flush and automatic native-log callbacks are used; no reflection, sampler freeze
or callback replacement. An empty, dropped, failed or silently inactive profile fails the probe.

Pyroscope's HTTP readiness does not guarantee immediate first-query visibility. A cold 2.4.3
backend in this environment needed additional startup time before ProfileTypes exposed ingested
data; the runner allows up to 300 seconds for readback and saves raw responses. This wait is
outside the captured workload and does not relax accuracy or sample-volume thresholds.

## Evidence and limits

Keep the complete manifest, all 18 oracle/spec/Querier/result files and the summary. The oracle
contains each cycle's measured durations/order, runtime versions and profiler diagnostics. Startup
or aborted setup probes are not completed matrix results and must not be promoted to passes.

This establishes aggregate wall-time attribution for the recorded CLI workloads/runtime/revisions.
It does not establish arbitrary C-call timelines (core ADR 11), CPU-mode accuracy, low-rate request
sampling representativeness, FPM/RR/Swoole accuracy, overhead, production UID behavior on another
host, tail latency, stability or final-RC certification. Revisit affected evidence when the final
candidate changes these paths. Retain historical measurements as measurements of their own pins.

The report figure is optional and requires Matplotlib (not needed for capture or validation):

```bash
python3 scripts/share-accuracy/plot.py reports/<report>/summary.json errors.svg
```
