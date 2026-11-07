#!/usr/bin/env python3
"""Summarize soak RSS/CPU time series + k6 summary into a markdown report."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path


def load_stats(path: Path) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    if not path.is_file():
        return rows
    with path.open() as f:
        for row in csv.DictReader(f):
            try:
                rows.append(
                    {
                        "ts": float(row["ts_unix"]),
                        "cpu": float(row["cpu_percent"]),
                        "rss": float(row["mem_usage_bytes"]),
                    }
                )
            except (KeyError, ValueError):
                continue
    return rows


def window(rows: list[dict[str, float]], start: float, end: float) -> list[dict[str, float]]:
    return [r for r in rows if start <= r["ts"] < end]


def series_summary(rows: list[dict[str, float]], label: str) -> dict[str, float | int | str | None]:
    if len(rows) < 2:
        return {
            "label": label,
            "samples": len(rows),
            "duration_h": None,
            "rss_first_avg": None,
            "rss_last_avg": None,
            "rss_delta_bytes": None,
            "rss_delta_pct": None,
            "rss_min": None,
            "rss_max": None,
            "cpu_avg": None,
            "cpu_max": None,
            "verdict": "insufficient samples",
        }

    t0, t1 = rows[0]["ts"], rows[-1]["ts"]
    span = max(t1 - t0, 1.0)
    # Compare first vs last hour (or first/last 10% if shorter than 2h).
    win = min(3600.0, span * 0.1) if span < 7200 else 3600.0
    first = window(rows, t0, t0 + win) or rows[: max(1, len(rows) // 10)]
    last = window(rows, t1 - win, t1 + 1) or rows[-max(1, len(rows) // 10) :]

    rss_first = statistics.fmean(r["rss"] for r in first)
    rss_last = statistics.fmean(r["rss"] for r in last)
    delta = rss_last - rss_first
    pct = (delta / rss_first * 100.0) if rss_first else 0.0
    cpus = [r["cpu"] for r in rows]
    rss_all = [r["rss"] for r in rows]

    # Soft heuristic: >20% growth and >8 MiB absolute → growth concern.
    if delta > 8 * 1024 * 1024 and pct > 20:
        verdict = "growth concern"
    elif abs(pct) <= 10 or abs(delta) <= 4 * 1024 * 1024:
        verdict = "stable (within noise)"
    else:
        verdict = "mild drift — inspect series"

    return {
        "label": label,
        "samples": len(rows),
        "duration_h": round(span / 3600.0, 3),
        "rss_first_avg": int(rss_first),
        "rss_last_avg": int(rss_last),
        "rss_delta_bytes": int(delta),
        "rss_delta_pct": round(pct, 2),
        "rss_min": int(min(rss_all)),
        "rss_max": int(max(rss_all)),
        "cpu_avg": round(statistics.fmean(cpus), 3),
        "cpu_max": round(max(cpus), 3),
        "verdict": verdict,
    }


def fmt_mib(n: float | int | None) -> str:
    if n is None:
        return "—"
    return f"{n / (1024 * 1024):.2f} MiB"


def k6_bits(summary: dict) -> dict[str, float | None]:
    metrics = summary.get("metrics") or {}
    dur = metrics.get("http_req_duration") or {}
    reqs = metrics.get("http_reqs") or {}
    failed = metrics.get("http_req_failed") or {}
    fail = failed.get("value")
    if fail is None:
        fail = failed.get("rate")
    return {
        "rps": reqs.get("rate"),
        "fail": float(fail) if fail is not None else None,
        "p95": dur.get("p(95)"),
        "p99": dur.get("p(99)"),
        "med": dur.get("med"),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--k6", type=Path, required=True)
    ap.add_argument("--app-stats", type=Path, default=None)
    ap.add_argument("--reader-stats", type=Path, default=None)
    # Legacy aliases
    ap.add_argument("--fpm-stats", type=Path, default=None)
    ap.add_argument("--drain-stats", type=Path, default=None)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--repo-sha", default="unknown")
    ap.add_argument("--host", default="")
    ap.add_argument("--rate", default="")
    ap.add_argument("--duration", default="")
    ap.add_argument("--sample-rate", default="0.1")
    ap.add_argument("--runtime", default="fpm", choices=("fpm", "rr", "swoole"))
    ap.add_argument("--reader", default="drain")
    ap.add_argument("--stack-depth", default="0")
    ap.add_argument("--app-service", default="")
    ap.add_argument("--reader-service", default="")
    args = ap.parse_args()

    app_stats = args.app_stats or args.fpm_stats
    reader_stats = args.reader_stats or args.drain_stats
    if app_stats is None or reader_stats is None:
        raise SystemExit("summarize-soak: need --app-stats/--reader-stats (or legacy --fpm-stats/--drain-stats)")

    runtime_label = {"rr": "RoadRunner", "swoole": "Swoole", "fpm": "PHP-FPM"}[args.runtime]
    profiler = (
        "`ContinuousProfiler`"
        if args.runtime == "swoole"
        else "`UnitOfWorkProfiler`"
    )
    app_svc = args.app_service or {
        "fpm": "app-fpm",
        "rr": "app-rr",
        "swoole": "app-swoole",
    }[args.runtime]
    reader_svc = args.reader_service or (
        "app-agent" if args.reader == "agent" else "app-drain"
    )

    summary = json.loads(args.k6.read_text()) if args.k6.is_file() else {}
    k6 = k6_bits(summary)
    app = series_summary(load_stats(app_stats), app_svc)
    reader = series_summary(load_stats(reader_stats), reader_svc)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    lines = [
        f"# Report: soak — {now[:10]}",
        "",
        "Methodology: [METHOD.md](../../METHOD.md) (soak / RSS·CPU growth). "
        "Limitations: [LIMITATIONS.md](../../LIMITATIONS.md).",
        "",
        f"Raw artifacts: `{args.out.parent.name}/`.",
        "",
        "## Identity",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| Date (UTC) | {now} |",
        f"| This repo SHA | `{args.repo_sha}` |",
        "| Tracewick version | Packagist `0.1.0` (stand pin) |",
        f"| Host | {args.host or '—'} |",
        "| Make target | `make bench-soak` |",
        "",
        "## Pins",
        "",
        "| Component | Value |",
        "| --- | --- |",
        "| k6 image | `grafana/k6:1.8.2` |",
        f"| RUNTIME | `{args.runtime}` ({runtime_label}) |",
        f"| Profiler | {profiler} + `SpoolSink` |",
        f"| READER | `{args.reader}` |",
        f"| WORK_STACK_DEPTH | {args.stack_depth} |",
        f"| RATE | {args.rate} req/s |",
        f"| DURATION | {args.duration} |",
        f"| sampleRate | {args.sample_rate} |",
        "| STATS_INTERVAL | see run meta / CSV spacing |",
        "",
        "## k6 (layer A, soak window)",
        "",
        "| Metric | Value |",
        "| --- | --- |",
    ]
    lines.append(
        f"| Achieved RPS | {k6['rps'] if k6['rps'] is not None else '—'} |"
    )
    if k6["fail"] is not None:
        lines.append(f"| http_req_failed | {(k6['fail'] * 100):.3f}% |")
    else:
        lines.append("| http_req_failed | — |")
    if k6["med"] is not None:
        lines.append(f"| Latency med | {k6['med']:.2f} ms |")
    else:
        lines.append("| Latency med | — |")
    if k6["p95"] is not None:
        lines.append(f"| Latency p95 | {k6['p95']:.2f} ms |")
    else:
        lines.append("| Latency p95 | — |")
    if k6["p99"] is not None:
        lines.append(f"| Latency p99 | {k6['p99']:.2f} ms |")
    else:
        lines.append("| Latency p99 | — |")
    lines += [
        "",
        "## RSS / CPU time series",
        "",
        "| Service | Samples | Hours | RSS first→last | Δ RSS | Δ % | RSS min/max | CPU avg/max | Verdict |",
        "| --- | ---: | ---: | --- | --- | ---: | --- | --- | --- |",
    ]

    for s in (app, reader):
        lines.append(
            "| {label} | {samples} | {duration_h} | {a} → {b} | {d} | {p} | {mn} / {mx} | {ca} / {cm} | {v} |".format(
                label=s["label"],
                samples=s["samples"],
                duration_h=s["duration_h"] if s["duration_h"] is not None else "—",
                a=fmt_mib(s["rss_first_avg"]),
                b=fmt_mib(s["rss_last_avg"]),
                d=fmt_mib(s["rss_delta_bytes"]),
                p=s["rss_delta_pct"] if s["rss_delta_pct"] is not None else "—",
                mn=fmt_mib(s["rss_min"]),
                mx=fmt_mib(s["rss_max"]),
                ca=s["cpu_avg"] if s["cpu_avg"] is not None else "—",
                cm=s["cpu_max"] if s["cpu_max"] is not None else "—",
                v=s["verdict"],
            )
        )

    lines += [
        "",
        "## What we proved / did not measure",
        "",
        f"- Proved (if verdicts stable): no large RSS climb on `{app_svc}` / `{reader_svc}` "
        f"({runtime_label} + {profiler}, reader=`{args.reader}`) under moderate fixed RPS for the soak window.",
        "- Did **not** measure: overhead A/B deltas, spool chaos, 1k+ RPS ceiling, multi-host isolation.",
        "",
    ]

    args.out.write_text("\n".join(lines))
    print(args.out.read_text())


if __name__ == "__main__":
    main()
