# OTel callback preflight — 2026-11-17

## Result

The recording SDK context path worked in the exercised sequential cases. The cold callback autoload gap has a separate core fix, [PR #84](https://github.com/tracewick/tracewick/pull/84); it is not merged or released by this report. Neither result implements the proposed correlation-aware model or accepts [ADR 14 / PR #81](https://github.com/tracewick/tracewick/pull/81).

At 100 Hz, the small differences were not resolved reliably against this shared-host scatter. At 1000 Hz, paired median additional total CPU versus the batched sampler was **7.69% at depth 48** and **8.42% at depth 256**. Individual pairs included negative changes and large positive outliers: these are descriptive preliminary measurements, not a precise production budget.

The work-only interval also matters: at 1000 Hz its paired median increase was **10.29% / 23.72%** at depths 48/256. The batched path postpones much of its PHP aggregation until final flush; one-entry callbacks perform that work during application execution. Total intervals below include final flush so that postponed work is not omitted. Do not describe this as only the cost of a cheap SDK getter.

## Method and pins

Methodology: [METHOD.md](../METHOD.md). [Reproduction](../experiments/otel-callback/README.md) · [raw measurements](2026-11-17-otel-callback-preflight/overhead.json).

This fixed-work CLI experiment replaces k6 only for isolating in-process callback cost. It measures no HTTP latency distribution, RPS, spool drain capacity or backend performance. Every mode runs the same 71,409,363 arithmetic iterations under the same active recording SDK span; profiling is effectively 100% of the measured window. No linear conversion to a 0.1 request sample rate is claimed.

| Component | Pin / setting |
| --- | --- |
| Core | 232c5e009514c8ee840bc4f131fe61c6347e1f69 (cold bootstrap fix, PR #84) |
| Benchmarks base | 472be2566a1d03d0f5f636b31ea7e84dca0f73c1 |
| PHP / Excimer | 8.5.12 / 1.2.7 |
| OTel SDK / API / context | 1.16.1 / 1.11.0 / 1.6.0; isolated Composer lock |
| Environment | Shared managed cloud environment; Intel Xeon Platinum 8573C; Linux 6.18.57 x86_64 |
| Visible resources | CPU quota 200000/100000 (2 CPUs); visible MemTotal 10,207,480 kB, not a dedicated-host RAM claim |
| PHP execution | PCOV disabled, CLI opcache disabled, no strace in timing runs |
| Workload | CPU-bound integer loop at a recursive depth that reaches configured caps 48/256 |
| Sampling | wall; 100/1000 Hz; batched threshold 10,000 or immediate threshold 1 |
| Repetitions | 7 rounds × 4 modes × 4 settings = 112 rows; seed 20261117 |
| Timing | 20:48:30–20:49:35 UTC; approximately 500 ms off-mode calibration target |

Four modes: off; real batched sampler; immediate callback with observer wrapper but no context read; the same immediate wrapper plus local trace/span context read and pair construction. Start, stop and final sampler flush are included in total wall/CPU times. SDK setup, export and worker process startup are excluded. Fresh process per row; randomized mode order inside each round; all row checksums agree. Only the transient container hostname was removed from exported metadata; numerical rows are unchanged. The archived runner now omits that hostname and the separate SDK correctness script was subsequently extended; timing worker/bootstrap code is unchanged. The prototype wrapper adds dispatch overhead absent from an eventual direct integration. The future context-aware builder and wire encoding add unmeasured work.

Shared cgroup telemetry recorded two additional throttled periods and 12.239 ms additional throttled time over the campaign. Those counters may include neighboring work; they do not prove the process had a dedicated CPU. Raw rows expose the observed scatter.

## Total CPU time

Medians are in milliseconds for the same fixed work. Paired change is the median of seven OTel/batched ratios in the matching rounds; it is not the ratio of the two displayed marginal medians. Min/max describe those seven ratios, not a confidence interval.

| Depth | Hz | Off | Batched | Immediate | OTel | Paired OTel/batched | Pair min…max |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 48 | 100 | 499.69 | 506.01 | 502.45 | 508.26 | -0.29% | -14.36%…+2.92% |
| 48 | 1000 | 499.23 | 516.14 | 542.04 | 555.35 | +7.69% | -6.23%…+42.04% |
| 256 | 100 | 488.18 | 519.87 | 518.24 | 513.27 | -1.27% | -17.19%…+10.68% |
| 256 | 1000 | 510.60 | 611.02 | 641.79 | 661.41 | +8.42% | -4.63%…+40.64% |

## Wall time and placement of aggregation

All values below are milliseconds, except the two paired changes. Work time excludes final flush; total includes it.

| Depth | Hz | Off total | Batched total | OTel total | Work-only paired change | Total paired change |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 48 | 100 | 499.66 | 505.73 | 507.76 | +0.10% | -0.33% |
| 48 | 1000 | 503.71 | 518.26 | 546.55 | +10.29% | +6.95% |
| 256 | 100 | 490.41 | 520.35 | 514.12 | +0.48% | -1.20% |
| 256 | 1000 | 512.74 | 611.76 | 651.84 | +23.72% | +7.04% |

The immediate/no-read mode shows that callback frequency and eager aggregation are substantial parts of the difference. SDK-only paired changes were inconsistent in sign at depth 48, and around +2% at depth 256. This run cannot assign a stable isolated cost to the SDK getter.

## Real SDK and cold-bootstrap correctness

[SDK result](2026-11-17-otel-callback-preflight/sdk.json) · [SDK with rotation](2026-11-17-otel-callback-preflight/sdk-rotation.json) · [cold-rotation result](2026-11-17-otel-callback-preflight/cold-rotation.json).

- Actual recording type: OpenTelemetry\SDK\Trace\Span; valid unsampled local type: OpenTelemetry\SDK\Trace\NonRecordingSpan.
- 378 native event weight equals 378 batch weight; next flush weight 0. Nine marked phases observed, zero wrong context associations.
- Spans are created while the profiler is already running, not only activated after preconstruction.
- Cases: no span, parent, child, parent restoration, ended-but-still-active child, unsampled local span, remote-parent omission, local child of remote parent, no context after detach. Ending a span does not detach its scope; this probe intentionally validates that distinction.
- Three spans were exported through SimpleSpanProcessor/InMemoryExporter, all outside callbacks. No callback-time warning or autoload was observed.
- Cold automatic rotation used normal core constructors without the prior manual preload list. 53 native weight equals 53 disk weight across 6 files, with no callback autoload or boundary violation.
- SDK + automatic rotation collected 2 profiles, preserving 405 native weight as 405 delivered weight; no sink call occurred inside the callback.
- Separate strace 6.1 checks recorded 358 SDK callbacks, 315 SDK-with-rotation callbacks and 65 cold-rotation callbacks with zero selected file/network/read/write/close calls inside them, excluding explicit marker writes. [Trace check summaries](2026-11-17-otel-callback-preflight/trace-checks.json). Raw traces remain local because they contain paths. The checked-in trace parser anchors syscall records so source text containing fwrite markers is not mistaken for an actual marker.
- Core maintained regressions run in fresh PHP processes, preventing PHPUnit class-loading order from hiding the cold paths. All three failed on the old source and passed with the fix. The complete local core suite/coverage passed: 838 tests, 5920 assertions, 8 existing optional skips. Local composer audit remains blocked by a proxy HTTP 403; CI status belongs to PR #84.

## What this does not prove

- No final correlation-aware aggregation, compact payload schema 2 or PHP/Go metadata delivery is implemented by this experiment.
- No memory leak, long-duration stability, known-function-share accuracy, custom context storage, full PHP/OTel compatibility matrix or concurrent span attribution claim.
- No production-wide overhead percentage, HTTP p99 claim, default-enable recommendation or extrapolation from CPU-only work to I/O-heavy applications.
- The running 72-hour soak uses its original pinned versions. These experiments neither alter it nor validate future correlation-enabled stability.

## Next decision

Review the sequential, opt-in design with its actual hot-path cost visible. Keep the cold-bootstrap fix independent. A production implementation needs maintained context/lifecycle regressions, explicit unsupported-context behavior, bounded correlation-aware stacks, shared wire fixtures and new measurements on its final code. No release gate is closed merely by accepting the proposal.
