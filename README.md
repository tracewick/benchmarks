# Tracewick Benchmarks

Load tests, soak runs, and reproducible benchmark stands for [Tracewick](https://github.com/tracewick/tracewick) — reports, charts, and an environment anyone can spin up to verify results.

This is a **sibling** of the library repo. Capacity / soak / load harness lives here. The library keeps only short summaries, selected screenshots, and a link.

Packagist: [`tracewick/tracewick`](https://packagist.org/packages/tracewick/tracewick) (pin recorded in every report).

## Quick start (M0)

```bash
git clone https://github.com/tracewick/benchmarks.git
cd benchmarks
cp .env.example .env   # optional
make up                # Pyroscope :4040, Grafana :3000 (loopback)
open http://127.0.0.1:3000
make down
```

**M1** adds the PHP workload + drain and `make bench-smoke` end-to-end. Until then, `generators/k6/smoke.js` is checked in and k6 is pinned as `grafana/k6:1.8.2` (see `make k6-version`).

## Documentation

| Doc | Purpose |
| --- | --- |
| [METHOD.md](METHOD.md) | How we measure (canon) |
| [LIMITATIONS.md](LIMITATIONS.md) | What we do not claim |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to change this repo |
| [scenarios/](scenarios/) | Named profiles |
| [reports/TEMPLATE.md](reports/TEMPLATE.md) | Report shape |

## Layout

```
stand/           compose support (Grafana provisioning, Toxiproxy, app placeholder)
generators/k6/   primary load scripts
scenarios/       scenario catalog
reports/         checked-in reports (+ TEMPLATE); local scratch under reports/_local/
```

## Make targets

| Target | Meaning |
| --- | --- |
| `make up` | Start Pyroscope + Grafana |
| `make up-chaos` | Also start Toxiproxy |
| `make down` | Stop and remove volumes |
| `make k6-version` | Print / run pinned k6 image |
| `make bench-smoke` | Short k6 smoke (needs M1 app) |
| `make collect-report` | Stash host meta under `reports/_local/` |

## Boundary with the library

| Here | There (`tracewick/tracewick`) |
| --- | --- |
| Capacity compose, k6, scenarios, reports | Unit / integration / Infection / smoke wiring |
| Long-lived charts and raw artifacts | Brief docs blurb + link + a couple of screenshots |
| Depend on Packagist / pinned git ref | Do not accept “add 10k RPS k6” PRs into the library |

## License

[Apache-2.0](LICENSE), same as Tracewick.
