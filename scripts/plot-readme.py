#!/usr/bin/env python3
"""Render the README's completed 72-hour observation from saved telemetry only."""
import gzip
import hashlib
import json
import os
import tempfile
from pathlib import Path

os.environ.setdefault('MPLCONFIGDIR', str(Path(tempfile.gettempdir()) / 'tracewick-readme-mpl'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'reports/2026-11-22-soak-rr-agent-72h'
OUTPUT = ROOT / 'reports/overview'
phases = [json.loads(line) for line in (SOURCE / 'phases.jsonl').read_text().splitlines()]
start = next(row['monotonic'] for row in phases if row['phase'] == 'steady')
fields = ('PHP worker', 'RoadRunner', 'Go agent', 'App cgroup', 'Reader cgroup')
sums = [{name: 0.0 for name in fields} for _ in range(72)]
counts = [0] * 72
with gzip.open(SOURCE / 'telemetry.jsonl.gz', 'rt') as stream:
    for row in map(json.loads, stream):
        if row['phase'] != 'steady':
            continue
        hour = int((row['monotonic'] - start) / 3600)
        assert 0 <= hour < 72
        counts[hour] += 1
        for role, comm, label in (('app', 'php', 'PHP worker'), ('app', 'rr', 'RoadRunner'),
                                  ('reader', 'tracewick-agent', 'Go agent')):
            process = next(p for p in row['containers'][role]['processes'] if p['comm'] == comm)
            sums[hour][label] += process['rss_bytes'] / 2**20
        sums[hour]['App cgroup'] += row['containers']['app']['memory_bytes'] / 2**20
        sums[hour]['Reader cgroup'] += row['containers']['reader']['memory_bytes'] / 2**20
assert all(count > 200 for count in counts), 'Missing or incomplete hourly evidence'
means = [{name: total[name] / count for name in fields} for total, count in zip(sums, counts)]
plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False,
                     'svg.hashsalt': 'tracewick-readme-72h', 'figure.facecolor': 'white'})
fig, axes = plt.subplots(1, 2, figsize=(11, 4.4), layout='constrained')
for axis, names, title in ((axes[0], fields[:3], 'Process RSS · hourly means'),
                           (axes[1], fields[3:], 'Cgroup memory · hourly means')):
    colors = {'PHP worker': '#2563eb', 'RoadRunner': '#d97706', 'Go agent': '#14856c',
              'App cgroup': '#2563eb', 'Reader cgroup': '#14856c'}
    for name in names:
        color = colors[name]
        axis.plot([hour + .5 for hour in range(72)], [m[name] for m in means],
                  label=name, color=color, linewidth=1.4)
    axis.set(title=title, xlabel='Hours since steady start', ylabel='MiB', xlim=(0, 72), ylim=(0, max(m[name] for m in means for name in names) * 1.4))
    axis.grid(alpha=.2)
    axis.legend(fontsize=9, loc='upper left')
fig.suptitle('Completed 72-hour RR + Go-agent soak · November 19–22 · 10 requests/s', fontsize=13)
path = OUTPUT / 'rr-agent-72h-memory.svg'
fig.savefig(path, metadata={'Date': None})
path.write_text(''.join(line.rstrip() + '\n' for line in path.read_text().splitlines()))
plt.close(fig)
inputs = [SOURCE / 'telemetry.jsonl.gz', SOURCE / 'phases.jsonl', SOURCE / 'identity.json']
manifest = {'scope': 'Hourly arithmetic means of every saved steady observation; process RSS and cgroup usage are separate.',
            'matplotlib': matplotlib.__version__, 'source_report': 'reports/2026-11-22-soak-rr-agent-72h.md',
            'sources': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},
            'image': str(path.relative_to(ROOT)), 'image_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'observations_per_hour': counts, 'hourly_means_mib': means}
(OUTPUT / 'rr-agent-72h-memory.json').write_text(json.dumps(manifest, indent=2) + '\n')
print('Rendered', path.relative_to(ROOT), 'from', sum(counts), 'steady observations')
