"""Paired, descriptive statistics for the window experiment."""
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

rows = [json.loads(line) for line in Path(sys.argv[1]).read_text().splitlines()]
cells = defaultdict(dict)
for r in rows:
    cell = cells[r['depth'], r['hz'], r['cycles']]
    key = r['round'], r['mode']
    if key in cell:
        raise ValueError('Duplicate worker')
    cell[key] = r
if len(rows) != 336 or len({r['checksum'] for r in rows}) != 1 or len(cells) != 8:
    raise ValueError('Incomplete campaign')

print('| Depth | Hz | Changes | Mode | CPU Δ %, median [min, max] | Work Δ % | Flush ms | RSS MiB | Callbacks/s | Changes/s | Linked weight % |')
print('|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|')
for (depth, hz, cycles), cell in sorted(cells.items()):
    for mode in ('off','batched','immediate','otel','deferred','history'):
        arm = [cell[i, mode] for i in range(1, 8)]
        def ratios(metric):
            return [100 * (r[metric] / cell[r['round'], 'batched'][metric] - 1) for r in arm]
        def median(metric, divisor=1):
            return statistics.median(r[metric] / divisor for r in arm)
        cpu = ratios('total_cpu_ns')
        work = statistics.median(ratios('work_wall_ns'))
        callback_rate = statistics.median(r['callbacks'] * 1e9 / r['total_wall_ns'] for r in arm)
        change_rate = statistics.median(r['changes'] * 1e9 / r['work_wall_ns'] for r in arm)
        linked = '—'
        if mode in ('deferred', 'history'):
            linked = f"{statistics.median(100 * (1 - r['unknown_weight'] / r['weight']) for r in arm):.1f}"
        print(f'| {depth} | {hz} | {cycles*2} | {mode} | {statistics.median(cpu):+.1f} '
              f'[{min(cpu):+.1f}, {max(cpu):+.1f}] | {work:+.1f} | {median("final_flush_ns",1e6):.2f} '
              f'| {median("max_rss_kib",1024):.1f} | {callback_rate:.0f} | {change_rate:.0f} | {linked} |')
