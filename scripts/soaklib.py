"""Linux/Docker soak telemetry and validity checks (standard library only)."""
from __future__ import annotations

import csv
import copy
import http.client
import json
import math
import os
import socket
import statistics
import subprocess
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROBE = (ROOT / 'scripts/soak_probe.sh').read_text()


def command(args, **kwargs):
    return subprocess.check_output(args, text=True, timeout=30, **kwargs).strip()


class UnixHTTP(http.client.HTTPConnection):
    def __init__(self, path):
        super().__init__('localhost', timeout=10)
        self.path = path

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.path)


class Docker:
    def __init__(self):
        host = os.environ.get('DOCKER_HOST') or command([
            'docker', 'context', 'inspect', '--format', '{{.Endpoints.docker.Host}}'])
        if not host.startswith('unix://'):
            raise ValueError('Observed soak requires local Linux Docker with a Unix socket')
        self.socket = host[7:]

    def get(self, path):
        conn = UnixHTTP(self.socket)
        try:
            conn.request('GET', path)
            response = conn.getresponse()
            body = response.read()
            if response.status != 200:
                raise RuntimeError(f'Docker {path}: HTTP {response.status}')
            return json.loads(body)
        finally:
            conn.close()

    def inspect(self, cid):
        return self.get(f'/containers/{cid}/json')

    def sample(self, cid, processes=False, allow_shared=False):
        info = self.inspect(cid)
        state = info['State']
        if not state['Running'] or state.get('OOMKilled'):
            raise RuntimeError(f'Container {cid[:12]} stopped or OOM-killed')
        stats = self.get(f'/containers/{cid}/stats?stream=false&one-shot=true')
        memory = stats['memory_stats']
        detail = memory.get('stats', {})
        cpu = stats['cpu_stats']
        started = datetime.fromisoformat(state['StartedAt'].replace('Z', '+00:00'))
        age = max(0, (datetime.now(timezone.utc) - started).total_seconds())
        implausible = cpu['cpu_usage']['total_usage'] / 1e9 > age * os.cpu_count() + 5
        if implausible and not allow_shared:
            raise ValueError('Implausible container CPU counter: shared/incorrect cgroup accounting')
        result = {
            'id': info['Id'], 'image': info['Image'], 'shared_cgroup_smoke': allow_shared,
            'started_at': state['StartedAt'], 'restarts': info['RestartCount'],
            'cpu_ns': cpu['cpu_usage']['total_usage'],
            'throttled_ns': cpu.get('throttling_data', {}).get('throttled_time', 0),
            'memory_bytes': memory['usage'],
            'anon_bytes': detail.get('anon', detail.get('total_rss', detail.get('rss'))),
            'file_bytes': detail.get('file', detail.get('total_cache', detail.get('cache'))),
            'memory_limit_bytes': memory.get('limit'),
            'pids': stats.get('pids_stats', {}).get('current'),
        }
        if processes:
            raw = subprocess.run(['docker', 'exec', '-i', '-u', '0', cid, 'sh'],
                                 input=PROBE, text=True, capture_output=True, timeout=15)
            if raw.returncode:
                raise RuntimeError(f'/proc probe failed for {cid[:12]} (exit {raw.returncode}): {raw.stderr.strip()}')
            result['processes'] = parse_processes(raw.stdout)
        return result


def parse_processes(raw):
    records = []
    current = None
    for line in raw.splitlines():
        if line.startswith('@ '):
            current = {'pid': int(line[2:])}
        elif line == '@end':
            if current is None or not {'start_ticks', 'rss_bytes', 'anon_bytes', 'fds',
                                       'threads', 'cpu_seconds'} <= current.keys():
                raise ValueError('Incomplete /proc record')
            records.append(current)
            current = None
        elif current is not None:
            if line.startswith(str(current['pid']) + ' ('):
                fields = line[line.rfind(')') + 2:].split()
                current['comm'] = line[line.find('(') + 1:line.rfind(')')]
                current['start_ticks'] = int(fields[19])
                current['cpu_seconds'] = (int(fields[11]) + int(fields[12])) / os.sysconf('SC_CLK_TCK')
            else:
                key, _, value = line.partition(':')
                if key in ('VmRSS', 'RssAnon', 'FDs', 'Threads'):
                    name = {'VmRSS': 'rss_bytes', 'RssAnon': 'anon_bytes',
                            'FDs': 'fds', 'Threads': 'threads'}[key]
                    current[name] = int(value.split()[0]) * (1024 if key in ('VmRSS', 'RssAnon') else 1)
    if current is not None or not records:
        raise ValueError('Empty or truncated /proc telemetry')
    return records


def get_json(url):
    with urllib.request.urlopen(url, timeout=5) as response:
        return json.load(response)


def k6_metrics(url):
    data = get_json(url + '/v1/metrics')['data']
    metrics = {item['id']: item['attributes']['sample'] for item in data}
    # k6 REST trend percentiles are cumulative checkpoints, not interval percentiles.
    return {'requests': metrics['http_reqs']['count'],
            'failed': metrics.get('http_req_failed', {}),
            'duration': metrics.get('http_req_duration', {}),
            'dropped': metrics.get('dropped_iterations', {}).get('count', 0)}


def prometheus(text):
    result = {}
    for line in text.splitlines():
        if not line or line.startswith('#'):
            continue
        key, value = line.split()
        if '{' not in key:
            result[key] = float(value)
    required = {'spool_files', 'spool_bytes', 'spool_oldest_age_seconds',
                'profiles_delivered_total', 'profiles_rejected_total',
                'profiles_retried_total', 'inflight_uploads'}
    if not required <= result.keys() or any(not math.isfinite(v) for v in result.values()):
        raise ValueError('Missing or invalid agent metrics')
    return result


def agent_metrics(url):
    with urllib.request.urlopen(url, timeout=5) as response:
        return prometheus(response.read().decode())


def process_identity(container):
    return sorted((p['pid'], p['start_ticks']) for p in container['processes'])


class Continuity:
    def __init__(self, interval):
        self.interval = interval
        self.previous = None

    def check(self, sample):
        previous = self.previous
        if previous:
            elapsed = sample['monotonic'] - previous['monotonic']
            if elapsed > max(self.interval * 2.5, self.interval + 30):
                raise ValueError(f'Telemetry gap: {elapsed:.1f}s')
            if sample['containers'].keys() != previous['containers'].keys():
                raise ValueError('Missing monitored container')
            for role, current in sample['containers'].items():
                old = previous['containers'][role]
                for key in ('id', 'started_at', 'restarts'):
                    if current[key] != old[key]:
                        raise ValueError(f'{role}: container restarted or was replaced')
                if current['cpu_ns'] < old['cpu_ns']:
                    raise ValueError(f'{role}: CPU counter reset')
                if 'processes' in current and process_identity(current) != process_identity(old):
                    raise ValueError(f'{role}: worker/process identity changed')
            if sample.get('agent') and previous.get('agent'):
                for key in ('profiles_delivered_total', 'profiles_rejected_total', 'profiles_retried_total'):
                    if sample['agent'][key] < previous['agent'][key]:
                        raise ValueError(f'Agent counter reset: {key}')
        self.previous = copy.deepcopy(sample)


def summarize(samples):
    rows = [s for s in samples if s['phase'] == 'steady']
    if len(rows) < 2:
        raise ValueError('Insufficient steady telemetry')
    span = rows[-1]['monotonic'] - rows[0]['monotonic']
    if span <= 0:
        raise ValueError('Invalid telemetry timestamps')
    output = {}
    for role in rows[0]['containers']:
        data = [s['containers'][role] for s in rows]
        window = min(3600, span * 0.1)
        first = [s['containers'][role] for s in rows if s['monotonic'] <= rows[0]['monotonic'] + window]
        last = [s['containers'][role] for s in rows if s['monotonic'] >= rows[-1]['monotonic'] - window]
        # Container memory and process RSS are deliberately separate measurements.
        mean = lambda group, key: statistics.fmean(r[key] for r in group)
        delta = mean(last, 'memory_bytes') - mean(first, 'memory_bytes')
        cpu = (data[-1]['cpu_ns'] - data[0]['cpu_ns']) / 1e9
        requests = rows[-1]['k6']['requests'] - rows[0]['k6']['requests']
        metrics = {
            'container_memory_first_bytes': mean(first, 'memory_bytes'),
            'container_memory_last_bytes': mean(last, 'memory_bytes'),
            'container_memory_delta_bytes': delta,
            'cpu_seconds': cpu, 'cpu_ms_per_request': cpu * 1000 / requests if requests and not data[0].get('shared_cgroup_smoke') else None,
            'throttled_seconds': (data[-1]['throttled_ns'] - data[0]['throttled_ns']) / 1e9,
        }
        if 'processes' in data[0]:
            process_cpu = sum(p['cpu_seconds'] for p in data[-1]['processes']) - sum(p['cpu_seconds'] for p in data[0]['processes'])
            metrics['process_cpu_ms_per_request'] = process_cpu * 1000 / requests if requests else None
            for key in ('rss_bytes', 'anon_bytes', 'fds', 'threads'):
                totals = [sum(p[key] for p in r['processes']) for r in data]
                # Least-squares slope uses the whole series, not only endpoints.
                xs = [(s['monotonic'] - rows[0]['monotonic']) / 3600 for s in rows]
                xm, ym = statistics.fmean(xs), statistics.fmean(totals)
                slope = sum((x - xm) * (y - ym) for x, y in zip(xs, totals)) / sum((x - xm)**2 for x in xs)
                metrics[key] = {'first': totals[0], 'last': totals[-1], 'max': max(totals),
                                'first_window_mean': statistics.fmean(sum(p[key] for p in r['processes']) for r in first),
                                'last_window_mean': statistics.fmean(sum(p[key] for p in r['processes']) for r in last),
                                'slope_per_hour': slope}
        output[role] = metrics
    return {'observed_seconds': span, 'services': output}


def write_report(directory, result):
    directory = Path(directory)
    (directory / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    lines = ['# Observed soak', '', 'Method: [METHOD.md](../../../METHOD.md).', '',
             f"Validity: **{result['status']}**", '',
             'A valid short run checks the harness only; it is not 72h evidence or proof of no leaks.', '']
    if result.get('error'):
        lines += ['Failure: ' + result['error'], '']
    summary = result.get('summary', {})
    if summary:
        lines += ['## Steady window', '', f"Observed: {summary['observed_seconds']:.1f} seconds.", '',
                  '| Service | Container memory Δ MiB | CPU ms/request | Process RSS slope MiB/h | Anonymous slope MiB/h |',
                  '| --- | ---: | ---: | ---: | ---: |']
        for role, values in summary['services'].items():
            slope = lambda key: f"{values[key]['slope_per_hour']/1048576:.3f}" if key in values else 'not collected'
            per_request = values['cpu_ms_per_request']
            cpu_text = f"{per_request:.3f}" if per_request is not None else 'not attributable'
            lines.append(f"| {role} | {values['container_memory_delta_bytes']/1048576:.3f} | "
                         f"{cpu_text} | {slope('rss_bytes')} | {slope('anon_bytes')} |")
    baseline = result.get('baseline_summary')
    if baseline:
        lines += ['', '## Short unprofiled baseline', '']
        for role, values in baseline['services'].items():
            lines.append(f"- {role}: {values['cpu_ms_per_request']} CPU ms/k6 HTTP request.")
    lines += ['', '## Evidence and interpretation', '',
              '- `identity.json`: resolved package/source references, image IDs, host and limits.',
              '- `telemetry.jsonl`: process identity, RSS/anonymous memory/FD/threads, cgroup CPU/memory/throttling, agent queue/delivery counters and k6 cumulative checkpoints.',
              '- `phases.jsonl`: phase boundaries; `*-k6.json`: complete per-phase latency/RPS/error summaries.',
              '- `hourly.json`: fixed-hour CPU/request and memory endpoints; latency checkpoints are cumulative, not hourly quantiles.',
              '- PID/start-time or container changes invalidate continuity. Resource limits remain enabled.',
              '- RSS includes shared mappings and retained allocator memory; a positive slope is a diagnosis trigger, not proof of a leak.',
              '- No goroutine/heap metrics are invented: current agent exposes delivery metrics only.',
              '- Writer diagnostics are available for the single RR worker; FPM/Swoole writer drops are not measured by this harness.',
              '- The short baseline uses a separate worker lifecycle and is not a full overhead capacity campaign.',
              '- No statistical symbol-share accuracy, chaos, maximum-RPS or production-readiness claim.', '']
    (directory / 'soak-report.md').write_text('\n'.join(lines))


def export_csv(directory, records):
    fields = ['ts', 'phase', 'role', 'container_memory_bytes', 'container_anon_bytes',
              'container_cpu_ns', 'shared_cgroup_smoke', 'process_rss_bytes',
              'process_anon_bytes', 'process_cpu_seconds', 'fds', 'threads',
              'k6_requests', 'pending_files', 'pending_bytes']
    with (Path(directory) / 'resource-series.csv').open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in records:
            for role, data in row['containers'].items():
                processes = data.get('processes')
                total = lambda key: sum(p[key] for p in processes) if processes else None
                writer.writerow(dict(zip(fields, [row['ts'], row['phase'], role,
                    data['memory_bytes'], data.get('anon_bytes'), data['cpu_ns'],
                    data.get('shared_cgroup_smoke', False), total('rss_bytes'), total('anon_bytes'),
                    total('cpu_seconds'), total('fds'), total('threads'), row['k6']['requests'],
                    row['spool']['pending_files'], row['spool']['pending_bytes']])))
