# Development runtime evidence

See the [report](../2026-11-22-development-runtime.md) and [method](../../METHOD.md).
The archive contains the six wall-budget arms, six fixed-operation arms,
request-level recovery samples and Symfony results/telemetry. The private original
snapshot is verified separately against SHA256 values collected on the VPS.

From this directory, check the published files and recompute summaries:

```bash
shasum -a 256 -c SHA256SUMS
tar -xzf raw.tar.gz
python3 analyze.py raw .
# Requires Matplotlib.
python3 plot.py
```

`raw-SHA256SUMS` records the original selected VPS files. Published identities
omit the host's uname hostname, and index directory paths are made relative.
Those intentionally edited files have different hashes. All other extracted
selected files retain their original hashes. `SHA256SUMS` covers the published
archive, summaries, scripts and figures; it excludes itself.

CPU/request uses matching observation endpoints. k6 quantiles use complete
measurement windows. Recovery quantiles use individual completed work requests,
classified by actual event timestamps. Reader counters reset at intentional
restarts, so the audit preserves per-epoch observed maxima instead of treating
those counters as one continuous series. The graceful-stop interval can include
acknowledgements after its last metric sample; summed observed deliveries do not
prove an exact unique backend-ingestion total.

The combined private snapshot imports Symfony evidence and the fixed calibration
from the campaign log directory into the raw layout used by the audit. Separate
original run and log/input SHA256 manifests were verified before packaging.
Inputs retain the fixture Composer manifest/lock, original bundle requirements,
runtime source fingerprints, final unit output and backend readbacks. The
memory-control input is the original fixture with artificial message sleep
removed and post-consumption transport-reset/GC/cache-release measurements added.
Its faster replay is a memory-release control, not an overhead comparison.
