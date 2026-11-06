# Tracewick Benchmarks

Load tests, soak runs, and reproducible benchmark stands for [Tracewick](https://github.com/tracewick/tracewick) — reports, charts, and an environment anyone can spin up to verify results.

This is a **sibling** of the library repo. Capacity / soak / load harness lives here. The library keeps only short summaries, selected screenshots, and a link.

Packagist: [`tracewick/tracewick`](https://packagist.org/packages/tracewick/tracewick) (pin recorded in every report).

## Quick start

Prerequisites: Docker with Compose v2, outbound network for the first image build (Packagist + pecl Excimer).

```bash
git clone https://github.com/tracewick/benchmarks.git
cd benchmarks
cp .env.example .env   # optional
make up                # build + Pyroscope + Grafana + PHP workload + drain
make bench-smoke       # wiring smoke (profiles → Pyroscope)
make bench-overhead    # M2: baseline vs on @ fixed RPS (~2× duration)
make bench-soak        # soak: RSS/CPU series (default 10 RPS / 72h; use tmux)
make down
```


| URL | What |
| --- | --- |
| http://127.0.0.1:8080/health | Workload liveness |
| http://127.0.0.1:8080/work | Profiled work unit |
| http://127.0.0.1:3000 | Grafana (anonymous Admin). **Explore → Profiles** (or Drilldown → Profiles), service `benchmarks-workload` |
| http://127.0.0.1:4040 | Pyroscope |

Pinned k6: `grafana/k6:1.8.2` (`make k6-version`). First `make up` compiles Excimer via PECL and may take several minutes.

## Documentation

| Doc | Purpose |
| --- | --- |
| [METHOD.md](METHOD.md) | How we measure (canon) |
| [LIMITATIONS.md](LIMITATIONS.md) | What we do not claim |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to change this repo |
| [scenarios/](scenarios/) | Named profiles |
| [reports/](reports/) | Checked-in reports + template |

## Layout

```
stand/           compose support + PHP workload (Packagist Tracewick)
generators/k6/   primary load scripts
scenarios/       scenario catalog
reports/         checked-in reports; local scratch under reports/_local/
```

## Make targets

| Target | Meaning |
| --- | --- |
| `make build` | Build PHP-FPM + nginx images |
| `make up` | Build + start full smoke stand |
| `make up-chaos` | Also start Toxiproxy |
| `make down` | Stop and remove volumes |
| `make k6-version` | Print / run pinned k6 image |
| `make bench-smoke` | Short k6 smoke + Pyroscope app check |
| `make bench-overhead` | M2 A/B at `RATE` req/s (default 20) for `DURATION` (default `2m`) |
| `make bench-spool-pressure` | M3: stop drain, fill spool, measure catch-up |
| `make bench-chaos` | M3: Toxiproxy latency toward Pyroscope |
| `make bench-soak` | Soak: fixed RPS + FPM/drain RSS·CPU (default `10` / `72h`) |
| `make bench-rps` | High-RPS pipeline: deep stacks + spool series (default `500` / `5m`) |
| `make collect-report` | Stash host meta under `reports/_local/` |

### Soak (manual / tmux)

Run on the VPS outside an IDE terminal so logout does not kill k6:

```bash
cd /root/benchmarks && git pull --ff-only && make up
tmux new -s soak
# inside tmux:
make bench-soak
# Detach: Ctrl-b d   |   Reattach: tmux attach -t soak
```

Defaults: `RATE=10`, `DURATION=72h`, `STATS_INTERVAL=60`, `sampleRate=0.1`. Override as env vars. Artifacts: `reports/_local/soak-<utc>/` and `soak-latest.md`.

### High-RPS pipeline (manual)

Uses the same `/work` wall budget (`WORK_BUSY_MS` / `WORK_SLEEP_MS`) as overhead/soak. Opt-in `WORK_STACK_DEPTH` deepens call stacks so spool payloads are larger (closer to a real app). Default scenarios keep `WORK_STACK_DEPTH=0`.

**Honesty:** these runs are **one instance** (typically app + drain + Pyroscope + k6 on a single VPS). The sustained RPS you publish is the **ceiling of that server configuration and synthetic work unit**, not “Tracewick handles N RPS everywhere” and not a multi-node fleet result. On the Timeweb 8 vCPU stand with depth-48 `/work` (~25 ms busy + 10 ms sleep, 32 FPM workers), overload probes showed ~760 achieved RPS with multi-second latency — so a clean hold is expected around **~700 RPS**, not 1.5–3k.

```bash
cd /root/benchmarks && git pull --ff-only
# first time after pull: rebuild FPM image (entrypoint / max_children)
make up
RATE=700 DURATION=5m PRE_VUS=500 MAX_VUS=2000 make bench-rps
# optional admission stress: DRAIN_MODE=off RATE=700 DURATION=2m ...
```

Artifacts: `reports/_local/rps-pipeline-<utc>/` and `rps-pipeline-latest.md`. Checked-in reports must repeat the single-instance / host-ceiling caveat.

Local run scratch: `reports/_local/`. Golden cloud reports:

- [overhead A/B](reports/2026-11-03-overhead-cloud.md)
- [spool pressure](reports/2026-11-03-spool-pressure-cloud.md)
- [chaos Pyroscope](reports/2026-11-03-chaos-pyroscope-cloud.md)
- [soak 72h (FPM static + UnitOfWorkProfiler)](reports/2026-11-03-soak-cloud.md)
- [high-RPS pipeline ~700 hold (8 vCPU, depth-48)](reports/2026-11-06-rps-pipeline-cloud.md)


## Boundary with the library

| Here | There (`tracewick/tracewick`) |
| --- | --- |
| Capacity compose, k6, scenarios, reports | Unit / integration / Infection / smoke wiring |
| Long-lived charts and raw artifacts | Brief docs blurb + link + a couple of screenshots |
| Depend on Packagist / pinned git ref | Do not accept “add 10k RPS k6” PRs into the library |

## License

[Apache-2.0](LICENSE), same as Tracewick.
