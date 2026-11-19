#!/usr/bin/env python3
"""Run isolated compatibility probes; retain failures as well as successes."""

import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import time
import uuid

HERE = Path(__file__).resolve().parent
MARKERS = {"probeAlpha", "probeBeta", "probeGamma", "probeDelta", "probeParent"}


def validate(data):
    errors = []
    if not data.get("zts") or data.get("php") != "8.5.12":
        errors.append("unexpected PHP/ZTS identity")
    latest = {row["actor"]: row for row in data["rows"]}
    for actor, row in latest.items():
        own = "probe" + actor.capitalize()
        seen = {k for k, v in row["markers"].items()} if isinstance(row["markers"], dict) else set()
        foreign = (seen & MARKERS) - {own}
        if foreign:
            errors.append(f"foreign markers in {actor}: {sorted(foreign)}")
        idle_cpu = data["scenario"] == "idle-cpu" and actor == "alpha" and data["event"] == "cpu"
        shutdown = data["scenario"] == "shutdown"
        if row["mode"] == "off":
            if row["events"]:
                errors.append("unprofiled runtime has events")
        elif not idle_cpu and not shutdown and (row["events"] < 3 or own not in seen):
            errors.append(f"insufficient own samples in {actor}")
        if row["callbacks"] and row["callback_actors"] != [actor]:
            errors.append(f"wrong callback interpreter in {actor}")
        diagnostic = row.get("diagnostics")
        if diagnostic:
            for key in ("droppedProfiles", "rejectedProfiles", "failedProfiles", "skippedProfiles",
                        "swallowedErrors", "samplerFailures"):
                if diagnostic[key]:
                    errors.append(f"{actor}: {key}={diagnostic[key]}")
            if diagnostic["inactiveSampler"] is not None:
                errors.append("inactive sampler")
        for labels in row.get("labels", []):
            if labels.get("actor") != actor:
                errors.append("profile labels crossed runtimes")
    if data["scenario"] in ("concurrent", "parent-only"):
        overlap = min(r["end_ns"] for r in data["rows"]) - max(r["start_ns"] for r in data["rows"])
        if overlap < 50_000_000:
            errors.append("less than 50ms common work overlap")
    if data["scenario"] == "idle-cpu":
        idle = latest["alpha"]["events"]
        if data["event"] == "cpu" and idle > 15:
            errors.append("idle thread accumulated >15ms CPU while sibling worked")
        if data["event"] == "wall" and idle < 150:
            errors.append("wall profiler did not account for blocking sleep")
    for item in data["spool"]:
        actor = item["labels"].get("actor")
        own = "probe" + str(actor).capitalize()
        seen = set(item["markers"]) if isinstance(item["markers"], dict) else set()
        if own not in seen or ((seen & MARKERS) - {own}):
            errors.append("spool has missing/foreign thread markers")
    if data["mode"] in ("uow", "continuous") and data["scenario"] != "shutdown":
        rows = latest.values() if data["scenario"] == "reuse" else data["rows"]
        if sum(r["events"] for r in rows) != sum(s["events"] for s in data["spool"]):
            errors.append("profile/spool weights differ")
    if data["scenario"] == "shutdown" and len(data["spool"]) != 4:
        errors.append("runtime shutdown did not flush all four profiles")
    if data["scenario"] == "churn" and max(data["threads_after_close"]) > 1:
        errors.append("native threads remain after closed worker runtimes")
    return sorted(set(errors))


def source_hash(core):
    h = hashlib.sha256()
    for file in sorted((core / "src").rglob("*.php")):
        h.update(str(file.relative_to(core)).encode() + b"\0" + file.read_bytes())
    return h.hexdigest()


def run_case(args, mode, event, scenario, repeat, wire="json", excimer=True):
    name = f"{mode}-{event}-{scenario}-{wire}-{repeat}"
    directory = args.output / name
    directory.mkdir(parents=True, exist_ok=False)
    container = "zts-probe-" + uuid.uuid4().hex[:12]
    cmd = ["docker", "run", "--rm", "--name", container, "--network", "none", "--cpus", "2",
           "--memory", "512m", "--pids-limit", "128", "-v", f"{HERE}:/probe:ro",
           "-v", f"{args.core}:/core:ro", "-v", f"{directory}:/output", args.image,
           "timeout", "--kill-after=2s", "20s", "php"]
    if not excimer:
        cmd += ["-n", "-d", "extension=parallel.so"]
    cmd += ["-d", "opcache.enable_cli=0", "/probe/case.php", mode, event, scenario, wire]
    start = time.monotonic()
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        code, stdout, stderr = result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired as error:
        code, stdout, stderr = 124, "", f"Host timeout: {error}"
    finally:
        subprocess.run(["docker", "rm", "-f", container], capture_output=True, timeout=10)
    (directory / "stdout.json").write_text(stdout)
    (directory / "stderr.txt").write_text(stderr)
    errors, data = [], None
    if code == 0:
        try:
            data = json.loads(stdout)
            errors = validate(data)
        except (ValueError, KeyError, TypeError) as error:
            errors = [f"invalid result: {error}"]
    else:
        errors = [f"process exit {code}"]
    unexpected = [line for line in stderr.splitlines()
                  if line and not line.startswith("Tracewick sample rate: 1 ")]
    if unexpected:
        errors.append("unexpected stderr")
    row = {"name": name, "mode": mode, "event": event, "scenario": scenario, "wire": wire,
           "excimer_loaded": excimer, "repeat": repeat, "exit": code,
           "elapsed_s": round(time.monotonic() - start, 3), "errors": errors,
           "pass": not errors, "result": data}
    print(json.dumps({k: v for k, v in row.items() if k != "result"}), flush=True)
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--core-ref", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--image", default="tracewick-zts-parallel:8.5")
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    args.core, args.output = args.core.resolve(), args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    before = source_hash(args.core)
    cases = [(m, e, "concurrent") for m in ("off", "native", "uow", "continuous") for e in ("wall", "cpu")]
    cases += [(m, e, "parent-only") for m in ("native", "uow") for e in ("wall", "cpu")]
    cases += [(m, e, "idle-cpu") for m in ("native", "uow") for e in ("wall", "cpu")]
    cases += [("uow", e, "reuse") for e in ("wall", "cpu")]
    cases += [(m, "wall", "churn") for m in ("native", "uow")]
    cases += [("uow", e, "shutdown") for e in ("wall", "cpu")]
    jobs = [(m, e, s, n) for m, e, s in cases for n in range(args.repeats)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        rows = list(pool.map(lambda item: run_case(args, *item), jobs))
    controls = [run_case(args, "off", "wall", "one", n, wire, False)
                for wire in ("array", "json") for n in range(args.repeats)]
    metadata = {"host_kernel": platform.release(), "architecture": platform.machine(),
                "core_ref": args.core_ref, "core_src_sha256": before,
                "source_unchanged": source_hash(args.core) == before,
                "image": subprocess.check_output(["docker", "image", "inspect", args.image,
                    "--format", "{{.Id}}"], text=True).strip(),
                "container_limits": {"cpus": 2, "memory_mib": 512, "pids": 128},
                "parallel_case_jobs": 2, "rows": rows, "array_transfer_controls": controls}
    (args.output / "results.json").write_text(json.dumps(metadata, indent=2) + "\n")
    if not metadata["source_unchanged"]:
        raise SystemExit("Core source changed during experiment")
    raise SystemExit(0 if all(r["pass"] for r in rows) else 1)


if __name__ == "__main__":
    main()
