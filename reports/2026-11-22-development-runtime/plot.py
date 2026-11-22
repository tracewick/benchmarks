"""Render the recorded preflight summaries; requires Matplotlib."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent

def load(name):
    return json.loads((ROOT / name).read_text())

def save_svg(fig, name):
    path = ROOT / name
    fig.savefig(path, metadata={'Date': None})
    path.write_text(''.join(line.rstrip() + '\n' for line in path.read_text().splitlines()))

plt.rcParams.update({'font.size': 10, 'axes.spines.top': False,
                     'axes.spines.right': False, 'figure.facecolor': 'white', 'svg.hashsalt': 'tracewick-development-runtime'})
fig, axes = plt.subplots(1, 2, figsize=(11, 4.3), layout='constrained')
for ax, filename, title in zip(axes, ('overhead-analysis.json', 'fixed-analysis.json'),
                              ('25 ms wall-budget work', 'Fixed operation count')):
    data = load(filename)
    phases = data['phases']
    for number in range(3):
        pair = phases[number * 2:number * 2 + 2]
        off = next(p for p in pair if not p['enabled'])
        on = next(p for p in pair if p['enabled'])
        ax.plot([number + 1 - .12, number + 1 + .12],
                [off['php_cpu_ms_per_request'], on['php_cpu_ms_per_request']],
                color='#b4bdc8', zorder=1)
        ax.scatter(number + 1 - .12, off['php_cpu_ms_per_request'], color='#536b88',
                   label='Off' if number == 0 else None, zorder=2)
        ax.scatter(number + 1 + .12, on['php_cpu_ms_per_request'], color='#c86c32',
                   label='On (sample rate 0.1)' if number == 0 else None, zorder=2)
    ax.set(title=title, xlabel='Pair', ylabel='PHP CPU ms / completed request', xticks=[1, 2, 3])
    ax.grid(axis='y', alpha=.2)
    ax.legend(frameon=False, fontsize=9)
fig.suptitle('Pinned development sources · one RR worker · 10 requests/s', fontsize=13)
fig.savefig(ROOT / 'paired-overhead.png', dpi=170)
save_svg(fig, 'paired-overhead.svg')
plt.close(fig)

recovery = load('recovery-analysis.json')
windows = recovery['fault_window_latencies']
labels = {'healthy': 'Healthy', 'backend_down': 'Backend\ndown',
          'backend_recovery': 'Backend\nrecovery', 'reader_stopped': 'Reader\nstopped',
          'reader_recovery': 'Reader\nrecovery', 'inflight_kill_and_pause': 'Inflight kill\n+ pause',
          'orphan_recovery': 'Orphan\nrecovery'}
fig, ax = plt.subplots(figsize=(11, 4.6), layout='constrained')
x = list(range(len(windows)))
ax.bar([i-.17 for i in x], [v['p95_ms'] for v in windows.values()], width=.34, label='p95', color='#536b88')
ax.bar([i+.17 for i in x], [v['p99_ms'] for v in windows.values()], width=.34, label='p99', color='#c86c32')
ax.set(xticks=x, xticklabels=[labels[k] for k in windows], ylabel='Request duration, ms',
       title='Independent request latency windows during recovery')
ax.grid(axis='y', alpha=.2)
ax.set_ylim(0, max(v['p99_ms'] for v in windows.values()) * 1.2)
ax.set_axisbelow(True)
ax.legend(frameon=False)
fig.savefig(ROOT / 'recovery-latencies.png', dpi=170)
save_svg(fig, 'recovery-latencies.svg')
plt.close(fig)
