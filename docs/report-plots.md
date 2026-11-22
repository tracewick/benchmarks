# Saved-report figures

The figures visualize existing evidence. Generating them does not run benchmarks, contact the
soak server, change measurements, or make old results evidence about a newer release.

## Historical report figures

Requires Python 3 and optional Matplotlib (3.10.8 used for the committed SVGs):

```bash
python3 scripts/plot-reports.py
python3 scripts/plot-reports.py --check
```

`--check` rerenders and verifies the exact figures, source hashes, derived numbers, embedded report
links and [provenance index](../reports/plot-manifest.json). Each measured report and its nested
raw-report Markdown use the same figure. The existing function-share plot has its separate
[reproduction command](../scripts/share-accuracy/README.md).

## Sources and semantics

- Overhead: baseline/on k6 quantiles and unfiltered container CPU/memory CSVs. Each arm's time axis
  starts at its own first sample; the arms are not simultaneous observations. No error bars or
  statistical certainty are inferred from one A/B pair. Lower latency in one arm can be noise.
- Soak: every saved container CPU/memory observation, including startup. Container memory usage is
  not per-process RSS, and a rising or flat curve alone does not identify or exclude a leak. The
  six-hour overview shows all three runtimes, with changes between first-hour and last-hour
  mean app-container usage of
  +3.6 MiB (FPM), +3.4 MiB (RoadRunner), and +1.9 MiB (Swoole). The November 8 RR data is the
  rerun after the stand switched to one profiler per worker (commit `8f7e372`); the earlier
  ~+1 GiB / 6h run with per-request construction is not checked in or plotted. Original
  historical verdicts/tables are retained; these figures do not certify them as leak tests.
- Spool/chaos/pipeline: saved file/byte counts. Claim/temp counts are a separate series, not added
  to the spool count. Dashed limits are soft admission settings decoded from the saved health
  response, never a hard disk bound. Some archived health files contain build output rather than
  JSON; their limit is omitted instead of invented. Catch-up seconds come from the saved scalar
  restart measurement, not a fitted drain curve.
- Signal weights: native/profile/spool counts and encoded/backend nanoseconds converted using
  the recorded sampling period. This visualizes total event conservation, not function-share
  accuracy or overhead.
- Deferred OTel research: all seven matched OTel/batched ratios at each depth/frequency, with
  their paired medians. Total CPU includes final flush; work-only wall time excludes it. These
  descriptive pairs are not confidence intervals or the cost of a shipped feature.
- The laptop smoke example has no raw k6 artifact. Its chart explicitly uses the approximate
  quantiles printed in the Markdown; it is illustrative wiring evidence, not a cloud benchmark.

Time-series lines connect saved observations without smoothing. Gaps greater than three times
the median positive sample interval are left blank. CPU is Docker's container percentage
(100% corresponds to one CPU), memory is shown in MiB (2^20 bytes). Historical pre-fix plots
carry historical labels and point to their original source/version context.

## README selections

The README now embeds the November 22 development-source paired CPU figure and
the completed November 19–22 RR/agent 72-hour memory overview. Their pins differ:
the short development campaign uses core `edb2427` / agent `d464fac`, while the
72-hour run uses core `55eb7bd` / agent `a15f0d3`. Neither is a released-RC claim.
The original November 6–8 overview files and their provenance remain historical.

Reproduce the development figure and its evidence hashes using its
[report instructions](../reports/2026-11-22-development-runtime/README.md).
Reproduce the README memory overview from the repository root:

```bash
python3 scripts/plot-readme.py
```

This streams every saved steady observation into 72 hourly arithmetic means.
It plots PHP/RR/agent process RSS separately from app/reader cgroup memory.
It does not plot a few selected endpoints or smooth the hourly means. The
[overview provenance](../reports/overview/rr-agent-72h-memory.json) records source
SHA256 values, counts, derived means, the output hash and Matplotlib version.
The original report retains interval-level figures and the full compressed data.
