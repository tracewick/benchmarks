#!/usr/bin/env python3
"""Validate complete measurement pairs and render their metrics."""

import argparse
import json
from itertools import groupby
from pathlib import Path


def read(path):
    return json.loads(path.read_text())


def run_metrics(arm):
    before = read(arm / "pre.json")
    after = read(arm / "post.json")
    warmup = read(arm / "warmup.json")["metrics"]
    load = read(arm / "measurement.json")["metrics"]
    clock_hz, *spool = (arm / "spool.txt").read_text().splitlines()
    start, end = (arm / "timestamps").read_text().split()
    runtime, mode, repeat = arm.name.split("-")
    cpu_ticks = after["cpu_ticks"] - before["cpu_ticks"]
    requests = load["http_reqs"]["count"]

    for stats in (warmup, load):
        if (stats["checks"]["fails"] != 0 or
            stats["checks"]["passes"] != stats["http_reqs"]["count"] or
            stats["dropped_iterations"]["count"] != 0 or stats["http_req_failed"]["value"] != 0):
            raise ValueError(f"Invalid load in {arm}")
    if any(before[key] != after[key] for key in ("pid", "start_ticks")):
        raise ValueError(f"Worker changed in {arm}")
    if (mode == "1") != bool(spool) or cpu_ticks < 0 or requests <= 0:
        raise ValueError(f"Invalid profiling or process counters in {arm}")

    return {
        "runtime": runtime,
        "repeat": int(repeat),
        "enabled": mode == "1",
        "start_epoch_utc": start,
        "end_epoch_utc": end,
        "worker_before": before,
        "worker_after": after,
        "clock_ticks_per_second": int(clock_hz),
        "warmup": warmup,
        "load": load,
        "requests": requests,
        "cpu_ms_per_request": cpu_ticks * 1000 / int(clock_hz) / requests,
        "rss_before_mib": before["rss_kib"] / 1024,
        "rss_after_mib": after["rss_kib"] / 1024,
        "p50_ms": load["http_req_duration"]["med"],
        "p95_ms": load["http_req_duration"]["p(95)"],
        "p99_ms": load["http_req_duration"]["p(99)"],
        "spool_files": len(spool),
        "spool_bytes": sum(int(row.rsplit(" ", 1)[1]) for row in spool),
    }


def render(runs):
    print("| Runtime | Pair | Profiling | Requests | CPU ms/req | RSS start → end, MiB | p50 / p95 / p99, ms | Spool files |")
    print("| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |")
    for row in runs:
        mode = "on" if row["enabled"] else "off"
        latency = " / ".join(f"{row[key]:.2f}" for key in ("p50_ms", "p95_ms", "p99_ms"))
        print(f"| {row['runtime']} | {row['repeat']} | {mode} | {row['requests']} | "
              f"{row['cpu_ms_per_request']:.2f} | {row['rss_before_mib']:.2f} → {row['rss_after_mib']:.2f} | "
              f"{latency} | {row['spool_files']} |")

    print("\n| Runtime | CPU/req delta | RSS at end delta | p95 delta | p99 delta |")
    print("| --- | ---: | ---: | ---: | ---: |")
    for runtime, pairs in groupby(pair_deltas(runs), key=lambda row: row[0]):
        deltas = [values for _, values in pairs]
        columns = " | ".join(f"{min(values):+.2f} to {max(values):+.2f} {unit}"
                             for values, unit in zip(zip(*deltas), ("%", "MiB", "ms", "ms")))
        print(f"| {runtime} | {columns} |")


def pair_deltas(runs):
    for runtime, runtime_runs in groupby(runs, key=lambda row: row["runtime"]):
        for repeat, pair_runs in groupby(runtime_runs, key=lambda row: row["repeat"]):
            pair = sorted(pair_runs, key=lambda row: row["enabled"])
            if [run["enabled"] for run in pair] != [False, True]:
                raise ValueError(f"Expected exactly one off and one on run for {runtime} pair {repeat}")
            off, on = pair
            yield runtime, (
                100 * (on["cpu_ms_per_request"] / off["cpu_ms_per_request"] - 1),
                on["rss_after_mib"] - off["rss_after_mib"],
                on["p95_ms"] - off["p95_ms"],
                on["p99_ms"] - off["p99_ms"],
            )

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", type=Path)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()

    runs = [run_metrics(arm) for arm in args.results.iterdir() if arm.is_dir()]
    if not runs:
        parser.error("No measurement arms found")
    runs.sort(key=lambda row: (row["runtime"], row["repeat"], row["start_epoch_utc"]))
    render(runs)
    if args.json:
        args.json.write_text(json.dumps(runs, indent=2) + "\n")


if __name__ == "__main__":
    main()
