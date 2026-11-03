# Contributing

Thanks for helping make Tracewick capacity numbers reproducible.

## Ground rules

- English for committed text (README, METHOD, reports, commits, PR titles).
- [Conventional Commits](https://www.conventionalcommits.org/).
- Small slices: stand → smoke → report → more scenarios.
- Follow [METHOD.md](METHOD.md). One factor per run; pin versions in reports.
- No secrets in git. Extend `.env.example` instead of committing `.env`.
- Prefer Apache-2.0–compatible contributions (same license as the library).

## Local workflow

```bash
cp .env.example .env   # optional overrides
make up                # observability + workload stand
make bench-smoke       # short k6 scenario (M1+)
make collect-report    # gather artifacts into reports/
make down
```

k6 runs via a pinned Docker image (`K6_IMAGE` in the Makefile). Host-installed k6 is optional and must match the pinned major/minor when used.

## Pull requests

- Link the scenario / report you changed.
- If you change methodology, update `METHOD.md` and call it out in the PR.
- Library API changes belong upstream in [tracewick/tracewick](https://github.com/tracewick/tracewick) — open an issue there rather than forking behavior here.
