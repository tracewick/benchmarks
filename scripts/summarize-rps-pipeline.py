#!/usr/bin/env python3
"""Summarize high-RPS pipeline hold: k6 + spool timeseries + optional docker stats."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path


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


def spool_bits(path: Path) -> dict[str, int | float | None]:
    rows: list[tuple[int, int, int, int]] = []
    if not path.is_file():
        return {
            "samples": 0,
            "files_max": None,
            "files_last": None,
            "bytes_max": None,
            "bytes_last": None,
        }
    with path.open() as f:
        for row in csv.DictReader(f):
            try:
                rows.append(
                    (
                        int(row["ts_unix"]),
                        int(row["files"]),
                        int(row["bytes"]),
                        int(row.get("claimed_or_tmp") or row.get("claimed") or 0),
                    )
                )
            except (KeyError, ValueError):
                continue
    if not rows:
        return {
            "samples": 0,
            "files_max": None,
            "files_last": None,
            "bytes_max": None,
            "bytes_last": None,
        }
    files = [r[1] for r in rows]
    sizes = [r[2] for r in rows]
    return {
        "samples": len(rows),
        "files_max": max(files),
        "files_last": files[-1],
        "bytes_max": max(sizes),
        "bytes_last": sizes[-1],
    }


def fmt_mib(n: int | None) -> str:
    if n is None:
        return "—"
    return f"{n / (1024 * 1024):.2f} MiB"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--k6", type=Path, required=True)
    ap.add_argument("--spool", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--repo-sha", default="unknown")
    ap.add_argument("--host", default="")
    ap.add_argument("--rate", default="")
    ap.add_argument("--duration", default="")
    ap.add_argument("--sample-rate", default="0.1")
    ap.add_argument("--stack-depth", default="0")
    ap.add_argument("--fpm-children", default="4")
    ap.add_argument("--path", default="/work")
    ap.add_argument("--drain", default="on")
    ap.add_argument("--reader", default="")
    args = ap.parse_args()
    reader = args.reader or ("off" if args.drain == "off" else "drain")

    summary = json.loads(args.k6.read_text()) if args.k6.is_file() else {}
    k6 = k6_bits(summary)
    spool = spool_bits(args.spool)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    fail_s = f"{(k6['fail'] * 100):.3f}%" if k6["fail"] is not None else "—"
    lines = [
        f"# Report: rps-pipeline — {now[:10]}",
        "",
        "Methodology: [METHOD.md](../../METHOD.md) (high-RPS pipeline / spool). "
        "Limitations: [LIMITATIONS.md](../../LIMITATIONS.md).",
        "",
        f"Raw artifacts: `{args.out.parent.name}/`.",
        "",
        "## Scope",
        "",
        f"- PHP-FPM + `UnitOfWorkProfiler` + `SpoolSink` + reader=`{reader}`.",
        f"- Path `{args.path}` with `WORK_STACK_DEPTH={args.stack_depth}` "
        "(deeper stacks → larger spool payloads; wall budget still `WORK_BUSY_MS`).",
        "- **Single instance:** sustained RPS is the ceiling of this host + work unit + FPM pool "
        "(often co-located k6), not a universal Tracewick SLO or multi-node fleet result.",
        "- Not ContinuousProfiler / RoadRunner / Swoole.",
        "",
        "## Identity",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| Date (UTC) | {now} |",
        f"| This repo SHA | `{args.repo_sha}` |",
        f"| Host | {args.host or '—'} |",
        "| Make target | `make bench-rps` |",
        "",
        "## Pins",
        "",
        "| Component | Value |",
        "| --- | --- |",
        f"| RATE (target) | {args.rate} req/s |",
        f"| DURATION | {args.duration} |",
        f"| sampleRate | {args.sample_rate} |",
        f"| WORK_STACK_DEPTH | {args.stack_depth} |",
        f"| PHP_FPM_MAX_CHILDREN | {args.fpm_children} |",
        f"| READER | {reader} |",
        f"| PATH | {args.path} |",
        "",
        "## k6",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Achieved RPS | {k6['rps'] if k6['rps'] is not None else '—'} |",
        f"| http_req_failed | {fail_s} |",
    ]
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
        "## Spool pipeline",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Samples | {spool['samples']} |",
        f"| Files max / last | {spool['files_max']} / {spool['files_last']} |",
        f"| Bytes max / last | {fmt_mib(spool['bytes_max'])} / {fmt_mib(spool['bytes_last'])} |",
        "",
        "## What we proved / did not measure",
        "",
        "- Pipeline under this arrival rate: HTTP fail-open, spool files/bytes trajectory, drain on/off as configured.",
        "- Did **not** claim a universal 3k RPS SLO; ceiling depends on host and stack depth.",
        "",
    ]
    args.out.write_text("\n".join(lines))
    print(args.out.read_text())


if __name__ == "__main__":
    main()
