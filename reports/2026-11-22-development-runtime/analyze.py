"""Audit the pinned development campaign and compute paired/fault-window metrics."""
import argparse
import datetime
import json
import statistics
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('raw', type=Path)
parser.add_argument('output', type=Path)
args = parser.parse_args()
raw = args.raw.resolve()
args.output.mkdir(parents=True, exist_ok=True)

def load(path):
    return json.loads(path.read_text())

def records(path):
    with path.open() as stream:
        return [json.loads(line) for line in stream]

def quantile(values, fraction):
    values = sorted(values)
    position = fraction * (len(values) - 1)
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    return values[lower] + (values[upper] - values[lower]) * (position - lower)

def process(row, role, name):
    return next(p for p in row['containers'][role]['processes'] if p['comm'] == name)

def cpu_ms(group, role, name):
    requests = group[-1]['k6']['requests'] - group[0]['k6']['requests']
    return (process(group[-1], role, name)['cpu_seconds'] -
            process(group[0], role, name)['cpu_seconds']) * 1000 / requests

def signature(container):
    return container['id'], container['started_at'], container['restarts']

def analyze_overhead(root, index_name, output_name, expected_iterations, minimum_span, calibration=None):
    index = load(root / index_name)
    assert len(index) == 6 and all(e['status'] == 'passed' for e in index), 'Incomplete A/B campaign'
    measurements = []
    for entry in index:
        directory = root / Path(entry['directory']).name
        result = load(directory / 'measurement.json')
        identity = load(directory / 'identity.json')
        runtime = identity['runtimes'][-1]
        assert runtime['reference'] == 'edb24275b48b6145216e8f8af34304819adf64f1'
        assert runtime['agent_reference'] == 'd464fac4a69a57b36dd171841012e69f3f5536ed'
        assert runtime['php'] == '8.4.27' and runtime['excimer'] == '1.2.7'
        assert identity['git_status'] == ''
        if index_name == 'fixed-index.json':
            assert identity['fixed_work']['iterations'] == calibration['iterations']
            assert identity['fixed_work']['checksum'] == calibration['checksum']
        phase = 'steady' if entry['enabled'] else 'baseline'
        rows = [r for r in records(directory / 'telemetry.jsonl') if r['phase'] == phase]
        settled = records(directory / 'settle-telemetry.jsonl')
        summary = load(directory / (phase + '-k6.json'))['metrics']
        assert abs(summary['iterations']['count'] - expected_iterations) <= 1
        assert summary['dropped_iterations']['count'] == 0 and summary['http_req_failed']['value'] == 0
        assert summary['checks']['value'] == 1
        assert result['drain']['pending_files'] == 0 and result['drain']['rejected_files'] == 0
        for row in settled + rows:
            assert row['health']['profiling_enabled'] is entry['enabled']
            assert row['health']['sample_rate'] == .1 and row['health']['rr_num_workers'] == 1
            assert row['health']['work_stack_depth'] == 48 and row['health']['excimer'] is True
            assert row['spool']['rejected_files'] == 0
            assert row['agent']['profiles_rejected_total'] == row['agent']['profiles_retried_total'] == 0
            if entry['enabled']:
                for key in ('droppedProfiles','skippedProfiles','failedProfiles','rejectedProfiles','swallowedErrors','samplerFailures'):
                    assert row['health']['diagnostics'][key] == 0
        for role in ('app', 'reader', 'pyroscope'):
            assert signature(settled[-1]['containers'][role]) == signature(rows[0]['containers'][role])
        for role, name in (('app', 'php'), ('app', 'rr'), ('reader', 'tracewick-agent')):
            assert (process(settled[-1],role,name)['pid'], process(settled[-1],role,name)['start_ticks']) == (process(rows[0],role,name)['pid'], process(rows[0],role,name)['start_ticks'])
        assert all(not c.get('shared_cgroup_smoke',False) for r in settled + rows for c in r['containers'].values())
        first, last = rows[0], rows[-1]
        elapsed = last['monotonic'] - first['monotonic']
        assert elapsed >= minimum_span
        gap = max(b['monotonic']-a['monotonic'] for a,b in zip(rows,rows[1:]))
        assert gap < 45
        assert all(len({signature(r['containers'][role]) for r in rows}) == 1 for role in first['containers'])
        for role, name in (('app', 'php'), ('app', 'rr'), ('reader', 'tracewick-agent')):
            assert len({(process(r, role, name)['pid'], process(r, role, name)['start_ticks']) for r in rows}) == 1
        if not entry['enabled']:
            assert all(r['health']['diagnostics'] is None or r['health']['diagnostics']['collectedProfiles'] == 0 for r in rows)
            assert first['agent']['profiles_delivered_total'] == last['agent']['profiles_delivered_total']
        values = {
            'number':entry['number'], 'enabled':entry['enabled'], 'directory':directory.name,
            'sample_count':len(rows), 'observed_seconds':elapsed, 'max_gap_seconds':gap,
            'work_iterations':summary['iterations']['count'],
            'p50_ms':summary['http_req_duration']['med'], 'p95_ms':summary['http_req_duration']['p(95)'],
            'p99_ms':summary['http_req_duration']['p(99)'],
            'observed_rps':(last['k6']['requests']-first['k6']['requests'])/elapsed,
            'php_cpu_ms_per_request':cpu_ms(rows,'app','php'),
            'rr_cpu_ms_per_request':cpu_ms(rows,'app','rr'),
            'agent_cpu_ms_per_request':cpu_ms(rows,'reader','tracewick-agent'),
            'php_last_minute_rss_mib':statistics.fmean(process(r,'app','php')['rss_bytes']/2**20 for r in rows if r['monotonic']>=last['monotonic']-60),
            'agent_last_minute_rss_mib':statistics.fmean(process(r,'reader','tracewick-agent')['rss_bytes']/2**20 for r in rows if r['monotonic']>=last['monotonic']-60),
            'peak_pending':max(r['spool']['pending_files'] for r in rows),
            'observed_delivery_delta': last['agent']['profiles_delivered_total'] - first['agent']['profiles_delivered_total'],
            'php_cgroup_memory_peak_mib': max(r['containers']['app']['memory_bytes'] for r in rows) / 2**20,
            'php_rss_peak_mib': max(process(r,'app','php')['rss_bytes'] for r in rows) / 2**20,
        }
        measurements.append(values)
    pairs = []
    for a,b in zip(measurements[::2],measurements[1::2]):
        off,on = (a,b) if not a['enabled'] else (b,a)
        delta = on['php_cpu_ms_per_request'] - off['php_cpu_ms_per_request']
        pairs.append({'off_number':off['number'],'on_number':on['number'],
                      'php_cpu_delta_ms':delta,'php_cpu_delta_percent':100*delta/off['php_cpu_ms_per_request'],
                      'p95_delta_ms':on['p95_ms']-off['p95_ms'],'p99_delta_ms':on['p99_ms']-off['p99_ms']})
    overhead = {'status':'valid measurement','phases':measurements,'pairs':pairs,
                'median_php_cpu_delta_percent':statistics.median(p['php_cpu_delta_percent'] for p in pairs),
                'range_php_cpu_delta_percent':[min(p['php_cpu_delta_percent'] for p in pairs),max(p['php_cpu_delta_percent'] for p in pairs)]}
    (args.output / output_name).write_text(json.dumps(overhead,indent=2)+'\n')
    return overhead

analyze_overhead(raw, 'overhead-index.json', 'overhead-analysis.json', 6000, 565)
calibration = load(raw / 'fixed-calibration.json')
assert 1000 <= calibration['iterations'] <= 10000000
checksum = 1
for _ in range(calibration['iterations']):
    checksum = (checksum * 1664525 + 1013904223) & 2147483647
assert checksum == calibration['checksum'], 'Calibration checksum differs from the independent integer oracle'
analyze_overhead(raw / 'fixed', 'fixed-index.json', 'fixed-analysis.json', 3000, 265, calibration)

recovery_directories = [p for p in raw.iterdir() if p.is_dir() and (p/'recovery.json').exists()]
assert len(recovery_directories)==1
directory = recovery_directories[0]
recovery = load(directory/'recovery.json')
assert recovery['status']=='passed'
events = records(directory/'events.jsonl')
timeline = {e['event']:e for e in events}
assert timeline['orphaned-claims']['filenames']
rows = records(directory/'telemetry.jsonl')
assert len({signature(r['containers']['app']) for r in rows})==1
for row in rows:
    assert row['k6']['failed']['rate']==0 and row['k6']['dropped']==0
    assert row['spool']['rejected_files']==0
    if row['agent']:
        assert row['agent']['profiles_rejected_total']==0
summary=load(directory/'steady-k6.json')['metrics']
assert abs(summary['iterations']['count']-21000)<=1
assert summary['http_req_failed']['value']==0 and summary['dropped_iterations']['count']==0
assert recovery['drain']['pending_files']==0 and recovery['drain']['rejected_files']==0
boundaries=[
    ('healthy',rows[0]['ts']),
    ('backend_down',timeline['backend-stop']['ts']),
    ('backend_recovery',timeline['backend-start']['ts']),
    ('reader_stopped',timeline['reader-stop']['ts']),
    ('reader_recovery',timeline['reader-start']['ts']),
    ('inflight_kill_and_pause',timeline['backend-pause-for-inflight']['ts']),
    ('orphan_recovery',timeline['reader-recover']['ts']),
]
latencies={name:[] for name,_ in boundaries}
with (directory/'steady-samples.json').open() as stream:
    for line in stream:
        event=json.loads(line)
        if event.get('type')!='Point':
            continue
        if event['metric']=='http_req_failed':
            assert event['data']['value']==0
        if event['metric']!='http_req_duration':
            continue
        point=event['data']
        if not point['tags'].get('name','').endswith('/work'):
            continue
        stamp=datetime.datetime.fromisoformat(point['time'].replace('Z','+00:00')).timestamp()
        phase=boundaries[0][0]
        for name,start in boundaries:
            if stamp>=start:
                phase=name
        latencies[phase].append(point['value'])
assert sum(map(len,latencies.values()))==summary['iterations']['count']
recovery['fault_window_latencies']={name:{'requests':len(v),'p50_ms':quantile(v,.5),'p95_ms':quantile(v,.95),'p99_ms':quantile(v,.99),'max_ms':max(v)} for name,v in latencies.items()}
recovery['fault_window_boundaries_utc'] = {name: datetime.datetime.fromtimestamp(start, datetime.timezone.utc).isoformat() for name,start in boundaries}
recovery['observed_reader_epochs'] = {}
for epoch in sorted({r['reader_epoch'] for r in rows}):
    metrics = [r['agent'] for r in rows if r['reader_epoch'] == epoch and r['agent']]
    if epoch == 0:
        metrics.append(timeline['reader-before-stop']['metrics'])
    elif epoch == 1:
        metrics.append(timeline['reader-before-kill']['metrics'])
    recovery['observed_reader_epochs'][str(epoch)] = {key: max(m[key] for m in metrics) for key in ('profiles_delivered_total','profiles_retried_total','profiles_rejected_total')}
recovery['app_resources'] = {
    'rss_first_mib': process(rows[0],'app','php')['rss_bytes'] / 2**20,
    'rss_last_mib': process(rows[-1],'app','php')['rss_bytes'] / 2**20,
    'rss_peak_mib': max(process(r,'app','php')['rss_bytes'] for r in rows) / 2**20,
    'cgroup_memory_peak_mib': max(r['containers']['app']['memory_bytes'] for r in rows) / 2**20,
}
recovery['orphaned_claims']=timeline['orphaned-claims']['filenames']
claim_epoch = max(int(name.rsplit('-', 1)[1]) for name in recovery['orphaned_claims'])
recovered = next(r for r in rows if r['ts'] >= claim_epoch + 600 and r['spool']['oldest_age_seconds'] < 30)
recovery['old_claim_no_longer_observed_after_seconds'] = recovered['ts'] - claim_epoch
recovery['old_claim_no_longer_observed_utc'] = datetime.datetime.fromtimestamp(recovered['ts'],datetime.timezone.utc).isoformat()
recovery['last_snapshot_diagnostics']=rows[-1]['health']['diagnostics']
(args.output/'recovery-analysis.json').write_text(json.dumps(recovery,indent=2)+'\n')
print('A/B pairs and request-level recovery windows independently audited')

symfony = {}
evidence = raw / 'symfony-evidence'
for mode in ('http', 'messenger'):
    result = load(evidence / (mode + '-delivery.json'))
    assert result['status'] == 'passed'
    assert result['php'] == '8.4.27' and result['excimer'] == '1.2.7'
    assert result['elapsed_seconds'] >= 1195
    for key in ('droppedProfiles', 'skippedProfiles', 'failedProfiles', 'rejectedProfiles', 'swallowedErrors', 'samplerFailures'):
        assert result['diagnostics'][key] == 0
    assert result['diagnostics']['collectedProfiles'] == result['diagnostics']['deliveredProfiles'] == result['delivered_in_reader']
    assert result['delivered_in_reader'] > 0
    assert result['final_spool']['pending_files'] == result['final_spool']['rejected_files'] == 0
    if mode == 'http':
        assert 5900 <= result['http'] <= 6000
        assert result['intentional_http_errors'] == (result['http'] + 30) // 31
    else:
        assert result['messages_handled'] + result['intentional_message_failures'] == 6000
        assert result['intentional_message_failures'] == (6000 + 30) // 31
    rows = records(evidence / (mode + '-telemetry.jsonl'))
    assert rows[-1]['monotonic'] - rows[0]['monotonic'] > 1170
    gap = max(b['monotonic'] - a['monotonic'] for a, b in zip(rows, rows[1:]))
    assert gap < 45
    assert all(len({signature(r['containers'][role]) for r in rows}) == 1 for role in rows[0]['containers'])
    graph = load(evidence / (mode + '-querier.json'))['flamegraph']
    weight = 0
    for level in graph['levels']:
        values = list(map(int, level['values']))
        assert len(values) % 4 == 0
        for offset in range(0, len(values), 4):
            _, width, own, name_id = values[offset:offset + 4]
            assert 0 <= own <= width and 0 <= name_id < len(graph['names'])
            if 'busyWork' in graph['names'][name_id]:
                weight += width
    assert weight > 0
    result['querier_busy_work_inclusive_ns'] = weight
    assert all(r['agent']['profiles_retried_total'] == 0 and r['agent']['profiles_rejected_total'] == 0 for r in rows)
    result['sample_count'] = len(rows)
    result['max_gap_seconds'] = gap
    result['resources'] = {}
    for role, name in (('app', 'php'), ('reader', 'tracewick-agent')):
        procs = [process(r, role, name) for r in rows]
        assert len({(p['pid'], p['start_ticks']) for p in procs}) == 1
        result['resources'][role] = {
            'rss_first_mib': procs[0]['rss_bytes'] / 2**20,
            'rss_minutes_2_3_mean_mib': statistics.fmean(process(r, role, name)['rss_bytes'] / 2**20 for r in rows if rows[0]['monotonic'] + 60 <= r['monotonic'] <= rows[0]['monotonic'] + 180),
            'rss_last_minute_mean_mib': statistics.fmean(process(r, role, name)['rss_bytes'] / 2**20 for r in rows if r['monotonic'] >= rows[-1]['monotonic'] - 60),
            'rss_last_mib': procs[-1]['rss_bytes'] / 2**20,
            'rss_peak_mib': max(p['rss_bytes'] for p in procs) / 2**20,
            'cgroup_memory_peak_mib': max(r['containers'][role]['memory_bytes'] for r in rows) / 2**20,
            'cpu_seconds': procs[-1]['cpu_seconds'] - procs[0]['cpu_seconds'],
            'fds_peak': max(p['fds'] for p in procs),
            'os_threads_peak': max(p['threads'] for p in procs),
        }
    symfony[mode] = result
(args.output / 'symfony-analysis.json').write_text(json.dumps(symfony, indent=2) + '\n')
print('Symfony outcomes, delivery reconciliation and process continuity independently audited')

probe = load(evidence / 'install-probe' / 'result.json')
assert probe['status'] == 'failed' and probe['composer_exit_code'] == 2
assert probe['core_source_version_for_resolution'] == '1.0.0-dev'
print('Original metadata source-1.0 compatibility failure retained separately')

check = load(evidence / 'check' / 'result.json')
assert check['status'] == 'passed' and check['http'] == 30
assert check['intentional_http_errors'] == 10
assert check['messages_handled'] == 19 and check['intentional_message_failures'] == 1
assert check['diagnostics']['collectedProfiles'] == check['diagnostics']['deliveredProfiles'] == 52
labels = load(evidence / 'check' / 'labels.json')
assert len(labels) == 52
assert all('uri' not in label and 'query' not in label for label in labels)
for route in ('preflight_work', 'preflight_parent', 'preflight_error'):
    assert sum(label.get('route') == route for label in labels) == 10
assert sum(label.get('message') == 'TracewickBench\\Preflight\\WorkMessage' for label in labels) == 20
assert sum(label.get('command') == 'preflight:work' for label in labels) == 2
print('The original 52 correctness profiles and their bounded labels independently audited')

control = load(raw / 'memory-control' / 'messenger' / 'result.json')
reset = load(raw / 'memory-control' / 'messenger' / 'memory-reset.json')
delivery = load(raw / 'memory-control' / 'delivery.json')
assert control['status'] == 'passed'
assert control['messages_handled'] == 5806 and control['intentional_message_failures'] == 194
assert control['diagnostics']['deliveredProfiles'] == delivery['writer'] == delivery['reader']['profiles_delivered_total']
assert delivery['final_spool']['pending_files'] == delivery['final_spool']['rejected_files'] == 0
assert delivery['reader']['profiles_retried_total'] == delivery['reader']['profiles_rejected_total'] == 0
for key in ('droppedProfiles', 'skippedProfiles', 'failedProfiles', 'rejectedProfiles', 'swallowedErrors', 'samplerFailures'):
    assert control['diagnostics'][key] == 0
reset['elapsed_seconds'] = control['elapsed_seconds']
reset['work_units'] = 6000
reset['writer_and_reader_profiles'] = delivery['writer']
reset['direct_transport_reset_php_used_drop_mib'] = (reset['before']['php_used_bytes'] - reset['after_transport_reset']['php_used_bytes']) / 2**20
reset['transport_reset_and_gc_php_used_drop_mib'] = (reset['before']['php_used_bytes'] - reset['after_cycle_collection']['php_used_bytes']) / 2**20
reset['rss_drop_after_reset_gc_and_cache_release_mib'] = (reset['before']['rss_bytes'] - reset['after']['rss_bytes']) / 2**20
(args.output / 'memory-control-analysis.json').write_text(json.dumps(reset,indent=2)+'\n')
print('Separate matched-count transport memory-release replay independently audited')
