#!/usr/bin/env python3
"""Optional static plots from preserved telemetry (requires matplotlib, not needed during load)."""
import argparse
import json
import os
import tempfile
from pathlib import Path

os.environ.setdefault('MPLCONFIGDIR', str(Path(tempfile.gettempdir()) / 'tracewick-matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

parser = argparse.ArgumentParser()
parser.add_argument('run_directory', type=Path)
args = parser.parse_args()
rows = [json.loads(line) for line in (args.run_directory / 'telemetry.jsonl').read_text().splitlines()]
start = rows[0]['monotonic']
x = [(r['monotonic'] - start) / 3600 for r in rows]
fig, axes = plt.subplots(3, 2, figsize=(13, 11), sharex=True)
for role in ('app', 'reader'):
    for field, axis, scale in [('rss_bytes', axes[0, 0], 1048576), ('anon_bytes', axes[0, 1], 1048576),
                               ('fds', axes[1, 0], 1), ('threads', axes[1, 1], 1)]:
        axis.plot(x, [sum(p[field] for p in r['containers'][role]['processes']) / scale for r in rows], label=role)
    times, cpu = [], []
    for a, b in zip(rows, rows[1:]):
        requests = b['k6']['requests'] - a['k6']['requests']
        if a['phase'] != b['phase'] or requests <= 0:
            continue
        old = sum(p['cpu_seconds'] for p in a['containers'][role]['processes'])
        new = sum(p['cpu_seconds'] for p in b['containers'][role]['processes'])
        times.append((b['monotonic'] - start) / 3600)
        cpu.append((new - old) * 1000 / requests)
    axes[2, 0].plot(times, cpu, label=role)
axes[2, 1].plot(x, [r['spool']['pending_files'] for r in rows], label='pending incl. claims/temp')
for axis, title in zip(axes.flat, ['Process RSS (MiB, shared mappings counted per process)',
                                  'Process anonymous memory (MiB)', 'Open file descriptors',
                                  'OS threads (not Go goroutines)', 'Process CPU ms/k6 HTTP request', 'Spool files']):
    axis.set_title(title, fontsize=10)
    axis.legend()
    axis.grid(alpha=.2)
    axis.set_xlabel('Hours since first observation')
phases = [json.loads(line) for line in (args.run_directory / 'phases.jsonl').read_text().splitlines()]
for axis in axes.flat:
    for phase in phases:
        at = (phase['monotonic'] - start) / 3600
        if at >= 0:
            axis.axvline(at, color='grey', alpha=.3, linewidth=.8)
fig.suptitle('Soak resource observations — inspect result.json for validity')
fig.tight_layout()
fig.savefig(args.run_directory / 'resources.png', dpi=150)
print(args.run_directory / 'resources.png')
