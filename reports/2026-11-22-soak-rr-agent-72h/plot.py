"""Render static figures from the compressed, interval-level observations."""
import gzip
import json
import os
import tempfile
from pathlib import Path

os.environ.setdefault('MPLCONFIGDIR', str(Path(tempfile.gettempdir()) / 'tracewick-matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

root = Path(__file__).resolve().parent
with gzip.open(root / 'telemetry.jsonl.gz', 'rt') as stream:
    rows = [r for r in map(json.loads, stream) if r['phase'] == 'steady']
phases = [json.loads(line) for line in (root / 'phases.jsonl').read_text().splitlines()]
start = next(p['monotonic'] for p in phases if p['phase'] == 'steady')
hours = [(r['monotonic'] - start) / 3600 for r in rows]
groups = [[r for r in rows if hour <= (r['monotonic']-start)/3600 < hour+1] for hour in range(72)]
centers = [hour+.5 for hour in range(72)]
plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False})

def rate(group, cpu):
    return (cpu(group[-1])-cpu(group[0])) * 1000 / (group[-1]['k6']['requests']-group[0]['k6']['requests'])

fig, axes = plt.subplots(3, 2, figsize=(13, 11), sharex=True)
for role, name, label, color in [('app','php','PHP worker','#2563eb'),
                                 ('app','rr','RoadRunner','#d97706'),
                                 ('reader','tracewick-agent','Go agent','#14856c')]:
    def process(row):
        return next(p for p in row['containers'][role]['processes'] if p['comm'] == name)
    for field, axis, scale in [('rss_bytes',axes[0,0],2**20),('anon_bytes',axes[0,1],2**20),
                                ('fds',axes[1,0],1),('threads',axes[1,1],1)]:
        axis.plot(hours,[process(r)[field]/scale for r in rows],color=color,lw=1,label=label)
    axes[2,0].plot(centers,[rate(group,lambda r:process(r)['cpu_seconds']) for group in groups],
                   color=color,label=label)
axes[2,1].plot(hours,[r['spool']['pending_files'] for r in rows],color='#7541b0',lw=.8,label='Pending files')
titles=['Process RSS (MiB)','Process anonymous memory (MiB)','Open file descriptors',
        'OS threads','Process CPU (ms/HTTP request, hourly)','Pending spool files']
for axis,title in zip(axes.flat,titles):
    axis.set_title(title)
    axis.set_xlim(0,72)
    axis.grid(alpha=.2)
    axis.legend(loc='best',fontsize=8)
    axis.set_xlabel('Hours since steady start')
fig.suptitle('72-hour RR and Go-agent soak · continuous worker · 10 RPS',fontsize=14)
fig.tight_layout()
fig.savefig(root/'process-resources.png',dpi=160)
plt.close(fig)

fig, axes = plt.subplots(2,2,figsize=(13,8),sharex=True)
for role,color in [('app','#2563eb'),('reader','#14856c'),('pyroscope','#d97706'),('generator','#7541b0')]:
    axes[0,0].plot(hours,[r['containers'][role]['memory_bytes']/2**20 for r in rows],label=role,color=color,lw=1)
    axes[0,1].plot(centers,[rate(group,lambda r:r['containers'][role]['cpu_ns']/1e9) for group in groups],label=role,color=color)
axes[1,0].plot(hours,[r['spool']['oldest_age_seconds'] for r in rows],label='Oldest pending file',color='#2563eb',lw=.8)
delivered = rows[0]['agent']['profiles_delivered_total']
axes[1,1].plot(hours,[(r['agent']['profiles_delivered_total']-delivered)/1000 for r in rows],
                label='Delivered profiles',color='#14856c')
for axis,title in zip(axes.flat,['Cgroup memory usage (MiB)','Container CPU (ms/HTTP request, hourly)',
                                 'Oldest pending file (seconds)','Agent delivery progress (thousands)']):
    axis.set_title(title)
    axis.set_xlim(0,72)
    axis.set_xlabel('Hours since steady start')
    axis.grid(alpha=.2)
    axis.legend(fontsize=8)
fig.suptitle('Co-located infrastructure and delivery observations',fontsize=14)
fig.tight_layout()
fig.savefig(root/'pipeline-resources.png',dpi=160)
print('Rendered process-resources.png and pipeline-resources.png')
