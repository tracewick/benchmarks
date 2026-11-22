"""Recompute resource trends and audit validity from the published telemetry."""
import gzip
import json
import statistics
import sys
from pathlib import Path

repo = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo / 'scripts'))
from soaklib import Continuity

run = Path(__file__).resolve().parent
out = run
with gzip.open(run / 'telemetry.jsonl.gz', 'rt') as stream:
    rows = [json.loads(line) for line in stream]
phases = [json.loads(line) for line in (run / 'phases.jsonl').read_text().splitlines()]
steady = [row for row in rows if row['phase'] == 'steady']
start = next(row for row in phases if row['phase'] == 'steady')
drain = next(row for row in phases if row['phase'] == 'drain')
a, b = steady[0], steady[-1]
duration = b['monotonic'] - a['monotonic']
requests = b['k6']['requests'] - a['k6']['requests']
first = [r for r in steady if r['monotonic'] <= a['monotonic'] + 3600]
last = [r for r in steady if r['monotonic'] >= b['monotonic'] - 3600]

guard = Continuity(15)
previous_phase = None
for row in rows:
    if previous_phase == 'baseline' and row['phase'] == 'warmup':
        guard = Continuity(15)
    guard.check({**row, 'containers': {k: v for k, v in row['containers'].items() if k != 'generator'}})
    previous_phase = row['phase']
assert all(r['k6']['failed']['rate'] == 0 and r['k6']['dropped'] == 0 for r in steady)
assert len({r['containers']['generator']['id'] for r in steady}) == 1
assert all(r['health']['sample_rate'] == .1 and r['health']['rr_num_workers'] == 1
           and r['health']['work_stack_depth'] == 48 and r['health']['profiling_enabled'] for r in steady)
assert all(r['spool']['rejected_files'] == 0 for r in rows)
assert all(r['agent']['profiles_rejected_total'] == 0 and r['agent']['profiles_retried_total'] == 0 for r in rows)
for key in ('droppedProfiles', 'skippedProfiles', 'failedProfiles', 'rejectedProfiles', 'swallowedErrors', 'samplerFailures'):
    assert all(r['health']['diagnostics'][key] == 0 for r in rows if r['phase'] != 'baseline')
assert all(r['spool']['pending_files'] == 0 for r in rows if r['phase'] == 'cooldown')

def slope(group, get):
    xs = [(r['monotonic'] - group[0]['monotonic']) / 3600 for r in group]
    ys = [get(r) for r in group]
    xm, ym = statistics.fmean(xs), statistics.fmean(ys)
    return sum((x-xm)*(y-ym) for x,y in zip(xs,ys)) / sum((x-xm)**2 for x in xs)

def cpu_per_request(group, get):
    return (get(group[-1]) - get(group[0])) * 1000 / (group[-1]['k6']['requests'] - group[0]['k6']['requests'])

processes = {}
for role, name in [('app', 'php'), ('app', 'rr'), ('reader', 'tracewick-agent')]:
    def process(row):
        return next(p for p in row['containers'][role]['processes'] if p['comm'] == name)
    identities = sorted({(process(r)['pid'], process(r)['start_ticks']) for r in steady})
    assert len(identities) == 1
    metrics = {'identity': identities[0]}
    for field in ('rss_bytes', 'anon_bytes', 'fds', 'threads'):
        get = lambda row: process(row)[field]
        metrics[field] = {
            'first_hour_mean': statistics.fmean(get(r) for r in first),
            'last_hour_mean': statistics.fmean(get(r) for r in last),
            'max': max(get(r) for r in steady), 'latest': get(b),
            'cooldown_last': get(rows[-1]),
            'slope_per_hour': slope(steady, get),
            'last_24h_slope_per_hour': slope([r for r in steady if r['monotonic'] >= b['monotonic'] - 86400], get)}
    get = lambda row: process(row)['cpu_seconds']
    metrics['cpu_ms_per_request'] = cpu_per_request(steady, get)
    metrics['first_hour_cpu_ms_per_request'] = cpu_per_request(first, get)
    metrics['last_hour_cpu_ms_per_request'] = cpu_per_request(last, get)
    processes[name] = metrics

containers = {}
for role in a['containers']:
    metrics = {}
    for field in ('memory_bytes', 'anon_bytes', 'file_bytes'):
        get = lambda row: row['containers'][role][field]
        metrics[field] = {'first_hour_mean': statistics.fmean(get(r) for r in first),
                          'last_hour_mean': statistics.fmean(get(r) for r in last),
                          'max': max(get(r) for r in steady)}
    get = lambda row: row['containers'][role]['cpu_ns'] / 1e9
    metrics['cpu_ms_per_request'] = cpu_per_request(steady, get)
    metrics['first_hour_cpu_ms_per_request'] = cpu_per_request(first, get)
    metrics['last_hour_cpu_ms_per_request'] = cpu_per_request(last, get)
    metrics['mean_vcpu'] = (get(b) - get(a)) / duration
    metrics['identity_count'] = len({(r['containers'][role]['id'],r['containers'][role]['started_at'],r['containers'][role]['restarts']) for r in steady})
    containers[role] = metrics

summary = {
    'verdict': 'pass for the pinned 72-hour RR and agent scenario',
    'steady_phase_seconds': drain['monotonic'] - start['monotonic'],
    'sampled_steady_seconds': duration,
    'steady_start_epoch': start['ts'], 'drain_start_epoch': drain['ts'],
    'preflight_and_final_drain_seconds': {p['phase']: phases[i+1]['monotonic'] - p['monotonic']
        for i,p in enumerate(phases[:-1]) if p['phase'] in ('preflight-drain','drain')},
    'phase_counts': {phase:sum(r['phase']==phase for r in rows) for phase in sorted({r['phase'] for r in rows})},
    'max_steady_gap_seconds': max(y['monotonic']-x['monotonic'] for x,y in zip(steady,steady[1:])),
    'mean_interval_seconds': duration/(len(steady)-1),
    'observed_rps': requests/duration,
    'steady_delivery_delta': b['agent']['profiles_delivered_total'] - a['agent']['profiles_delivered_total'],
    'warmup_through_cooldown_delivery_total': rows[-1]['agent']['profiles_delivered_total'],
    'final_diagnostics': rows[-1]['health']['diagnostics'],
    'spool_peak': {k:max(r['spool'][k] for r in steady) for k in a['spool']},
    'final_spool': rows[-1]['spool'], 'processes': processes, 'containers': containers,
    'phase_k6': {p:json.loads((run/(p+'-k6.json')).read_text())['metrics'] for p in ('baseline','warmup','steady')}
}
(out / 'analysis.json').write_text(json.dumps(summary, indent=2)+'\n')
print('Verified continuity and regenerated analysis.json')
