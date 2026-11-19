# RoadRunner soak interrupted by a process probe race

Methodology follows [METHOD.md](../METHOD.md) and the
[observed-soak runbook](../docs/soak.md).

## Outcome

The attempted 72-hour RR and Go-agent run is **invalid**. It stopped after
27.12 hours of steady observations with an empty-detail
`/proc probe failed` error. Final drain and cooldown did not run.
The raw evidence is retained locally under
`reports/_local/failed-20261119/soak-20261117T182006Z`.

The sampling window ran from 2026-11-17 18:31 UTC until the last successful
observation at 2026-11-18 21:38 UTC. Benchmarks used
`e4835846fd0ba04b895ea81c0bb4a128da82e103`, Tracewick used
`55eb7bdb91cd4269a86bb0dd8ce22a243e5486b4`, and the Go agent used
`a15f0d310ba6d5942e67b37d3c3c55dc1b3b8100`. Excimer 1.2.7 used
`23f541b9d970db0524a1b2506b4df727e5e59998`. The host had 2 vCPU,
3.8 GiB RAM and Ubuntu 26.04.1. The configuration used one RR worker,
depth 48, sample rate 0.1, target 10 RPS and 15-second observations.

## Observations before interruption

There were 6,266 steady snapshots, with a maximum gap of 16.10 seconds.
k6 recorded 976,223 HTTP requests, zero HTTP failures and zero dropped
iterations. The observed rate was 10.00 RPS. Cumulative p95 was 37.40 ms.
The queue peaked at nine files and four seconds of age. The agent delivered
97,851 profiles during the observed steady span, with zero retries or rejects.
The last complete observation contained two pending files.

| Process | First-hour mean RSS MiB | Last-hour mean RSS MiB | First-hour CPU ms/request | Last-hour CPU ms/request |
| --- | ---: | ---: | ---: | ---: |
| PHP worker | 28.398 | 28.406 | 25.754 | 25.704 |
| RoadRunner | 47.986 | 49.910 | 0.785 | 0.787 |
| Go agent | 13.648 | 14.084 | 0.0695 | 0.0697 |

PHP and agent identities remained continuous through the saved observations.
Later inspection found the containers still running, with zero restarts and
no OOM flags. The agent reported an empty queue after the interruption.
This later observation does not replace the missing final drain phase.

## Reproduction and correction

A separate burst of real PHP extension healthchecks reproduced a probe failure
on iteration 17. The shell trace showed a PHP process with an empty cmdline,
followed by failure to read its stat file after process exit.
The old probe had already emitted the record header. It exited with status 1
and suppressed the underlying error text.

This reproduces a failure path consistent with the interruption. The original
run did not save the failing probe's partial stdout or field-level context,
so its exact failing PID and read cannot be recovered.

The corrected probe buffers stat, status and descriptors before emitting the
record. It omits exiting transient processes and retains the existing identity
validator for missing or replaced workers. Read failures for a process that
remains present still fail collection, with PID and field diagnostics.
Deterministic tests cover process exit during reads, a live-process read failure,
and a descriptor-read failure.

The saved window shows stable PHP resources and modest agent memory changes.
It provides partial-duration observations. A fresh continuous 72-hour run is
required to complete the intended experiment.
