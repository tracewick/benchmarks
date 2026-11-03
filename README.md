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
| `make collect-report` | Stash host meta under `reports/_local/` |

Overhead artifacts land in `reports/_local/overhead-<timestamp>/` and `reports/_local/overhead-latest.md`. Copy a polished version into `reports/` when checking in a golden cloud run.

## Boundary with the library

| Here | There (`tracewick/tracewick`) |
| --- | --- |
| Capacity compose, k6, scenarios, reports | Unit / integration / Infection / smoke wiring |
| Long-lived charts and raw artifacts | Brief docs blurb + link + a couple of screenshots |
| Depend on Packagist / pinned git ref | Do not accept “add 10k RPS k6” PRs into the library |

## License

[Apache-2.0](LICENSE), same as Tracewick.
