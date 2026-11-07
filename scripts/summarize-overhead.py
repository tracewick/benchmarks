#!/usr/bin/env python3
"""Build a markdown overhead A/B report from k6 summaries + docker stats CSVs."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path


def k6_latency(summary: dict) -> dict[str, float | None]:
    m = summary.get("metrics", {}).get("http_req_duration", {})
    # k6 summary-export: trend values are flat keys on the metric object
    return {
        "avg": m.get("avg"),
        "med": m.get("med"),
        "p90": m.get("p(90)"),
        "p95": m.get("p(95)"),
        "p99": m.get("p(99)"),
        "max": m.get("max"),
    }


def k6_rps(summary: dict) -> float | None:
    reqs = summary.get("metrics", {}).get("http_reqs", {})
    if "rate" in reqs:
        return reqs["rate"]
    # older shape
    values = reqs.get("values") or {}
    return values.get("rate")


def k6_fail_rate(summary: dict) -> float | None:
    failed = summary.get("metrics", {}).get("http_req_failed", {})
    # k6 summary-export: Rate metrics expose the rate as "value" (0..1).
    if isinstance(failed.get("value"), (int, float)):
        return float(failed["value"])
    if "rate" in failed:
        return float(failed["rate"])
    values = failed.get("values") or {}
    if "rate" in values:
        return float(values["rate"])
    return None


def stats_agg(path: Path) -> dict[str, float | None]:
    if not path.is_file():
        return {"cpu_avg": None, "cpu_max": None, "rss_avg": None, "rss_max": None, "samples": 0}
    cpus: list[float] = []
    rss: list[int] = []
    with path.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                cpus.append(float(row["cpu_percent"]))
                rss.append(int(row["mem_usage_bytes"]))
            except (KeyError, ValueError):
                continue
    if not cpus:
        return {"cpu_avg": None, "cpu_max": None, "rss_avg": None, "rss_max": None, "samples": 0}
    return {
        "cpu_avg": round(statistics.fmean(cpus), 3),
        "cpu_max": round(max(cpus), 3),
        "rss_avg": int(statistics.fmean(rss)),
        "rss_max": max(rss),
        "samples": len(cpus),
    }


def fmt_ms(v: float | None) -> str:
    return "—" if v is None else f"{v:.2f} ms"


def fmt_pct(v: float | None) -> str:
    return "—" if v is None else f"{v:.3f}%"


def fmt_bytes(v: int | None) -> str:
    if v is None:
        return "—"
    mb = v / (1024 * 1024)
    return f"{mb:.1f} MiB"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--baseline-k6", type=Path, required=True)
    p.add_argument("--on-k6", type=Path, required=True)
    p.add_argument("--baseline-stats", type=Path, required=True)
    p.add_argument("--on-stats", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--repo-sha", default="")
    p.add_argument("--host", default="")
    p.add_argument("--rate", default="20")
    p.add_argument("--duration", default="2m")
    p.add_argument("--sample-rate", default="0.1")
    p.add_argument("--stack-depth", default="0")
    p.add_argument("--runtime", default="fpm", choices=("fpm", "rr"))
    p.add_argument("--reader", default="drain")
    args = p.parse_args()

    b = load_json(args.baseline_k6)
    o = load_json(args.on_k6)
    bl, ol = k6_latency(b), k6_latency(o)
    bs, os_ = stats_agg(args.baseline_stats), stats_agg(args.on_stats)
    svc = "app-rr" if args.runtime == "rr" else "app-fpm"
    runtime_label = "RoadRunner" if args.runtime == "rr" else "PHP-FPM"

    def delta_ms(a: float | None, b: float | None) -> str:
        if a is None or b is None:
            return "—"
        return f"{(b - a):+.2f} ms"

    def delta_pct_points(a: float | None, b: float | None) -> str:
        if a is None or b is None:
            return "—"
        return f"{(b - a):+.3f} pp"

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines = [
        f"# Report: overhead A/B — {now}",
        "",
        "Methodology: [METHOD.md](../METHOD.md). Limitations: [LIMITATIONS.md](../LIMITATIONS.md).",
        "",
        "## Identity",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| Date (UTC) | {now} |",
        f"| This repo SHA | `{args.repo_sha or 'unknown'}` |",
        "| Tracewick version | Packagist `0.1.0` |",
        f"| Host | {args.host or 'see uname in reports/_local'} |",
        "| Make target | `make bench-overhead` |",
        "",
        "## Pins",
        "",
        "| Component | Version |",
        "| --- | --- |",
        "| k6 image | `grafana/k6:1.8.2` |",
        "| PHP / Excimer | 8.4 / 1.2.6 |",
        "| Pyroscope | `grafana/pyroscope:2.4.2` |",
        f"| RUNTIME | `{args.runtime}` ({runtime_label}) |",
        f"| READER | `{args.reader}` |",
        f"| sampleRate (on) | `{args.sample_rate}` |",
        "| baseline | `TRACEWICK_ENABLED=0` (profiler not constructed) |",
        f"| RATE / duration | {args.rate} req/s / {args.duration} |",
        "| WORK_BUSY_MS / WORK_SLEEP_MS | 25 / 10 |",
        f"| WORK_STACK_DEPTH | {args.stack_depth} |",
        "",
        "## Results — A. Application overhead",
        "",
        "| Metric | baseline (off) | on (0.1) | delta (on − baseline) |",
        "| --- | --- | --- | --- |",
        f"| Latency med | {fmt_ms(bl['med'])} | {fmt_ms(ol['med'])} | {delta_ms(bl['med'], ol['med'])} |",
        f"| Latency p95 | {fmt_ms(bl['p95'])} | {fmt_ms(ol['p95'])} | {delta_ms(bl['p95'], ol['p95'])} |",
        f"| Latency p99 | {fmt_ms(bl['p99'])} | {fmt_ms(ol['p99'])} | {delta_ms(bl['p99'], ol['p99'])} |",
        f"| HTTP RPS (achieved) | {k6_rps(b) or '—'} | {k6_rps(o) or '—'} | |",
        f"| http_req_failed | {k6_fail_rate(b)} | {k6_fail_rate(o)} | |",
        f"| {svc} CPU avg | {fmt_pct(bs['cpu_avg'])} | {fmt_pct(os_['cpu_avg'])} | {delta_pct_points(bs['cpu_avg'], os_['cpu_avg'])} |",
        f"| {svc} CPU max | {fmt_pct(bs['cpu_max'])} | {fmt_pct(os_['cpu_max'])} | {delta_pct_points(bs['cpu_max'], os_['cpu_max'])} |",
        f"| {svc} RSS avg | {fmt_bytes(bs['rss_avg'])} | {fmt_bytes(os_['rss_avg'])} | |",
        f"| {svc} RSS max | {fmt_bytes(bs['rss_max'])} | {fmt_bytes(os_['rss_max'])} | |",
        "",
        f"Stats samples: baseline={bs['samples']}, on={os_['samples']} (docker stats on `{svc}`).",
        "",
        "## What we proved / did not measure",
        "",
        f"- Proved: relative overhead of Tracewick SpoolSink path vs profiler-not-wired on this synthetic `/work` unit ({runtime_label}).",
        f"- WORK_STACK_DEPTH={args.stack_depth}: 0 = shallow busyWork; >0 = deeper frames (larger profiles, same wall budget).",
        "- Did **not** measure: real app (DB/HTTP), soak/72h RSS growth, spool backpressure, chaos, multi-host isolation.",
        "- Absolute % is host-specific; compare delta columns, not marketing SLOs.",
        "",
    ]
    args.out.write_text("\n".join(lines) + "\n")
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
