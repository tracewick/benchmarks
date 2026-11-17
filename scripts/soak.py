#!/usr/bin/env python3
"""Observed soak runner. Requires Linux, local Docker, Compose v2, Python 3 and k6 image."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import re
import shlex
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

from soaklib import (ROOT, Continuity, Docker, agent_metrics, command, get_json,
                     k6_metrics, summarize, write_report, export_csv)


def seconds(value):
    parts = re.findall(r'(\d+(?:\.\d+)?)(ms|s|m|h)', value)
    if not parts or ''.join(n + u for n, u in parts) != value:
        raise ValueError(f'Invalid duration: {value}')
    result = sum(float(n) * {'ms': .001, 's': 1, 'm': 60, 'h': 3600}[u] for n, u in parts)
    if result <= 0:
        raise ValueError('Durations must be positive')
    return result


def pin(value):
    if not re.fullmatch(r'v?\d+\.\d+\.\d+(?:-[a-zA-Z0-9.-]+)?|dev-develop#[0-9a-f]{40}', value):
        raise ValueError('TRACEWICK_VERSION must be an exact version or dev-develop#<40-hex SHA>')
    return value


class Soak:
    def __init__(self):
        self.env = dict(os.environ)
        self.runtime = self.env.get('RUNTIME', 'rr')
        self.reader = self.env.get('READER', 'agent')
        if self.runtime not in ('fpm', 'rr', 'swoole') or self.reader not in ('agent', 'drain'):
            raise ValueError('RUNTIME=fpm|rr|swoole and READER=agent|drain required')
        self.package = pin(self.env['TRACEWICK_VERSION'])
        if self.reader == 'agent':
            ref = self.env.get('AGENT_REF', '')
            if ref:
                if not re.fullmatch('[0-9a-f]{40}', ref):
                    raise ValueError('AGENT_REF must be a full commit SHA')
                self.env['AGENT_BUILD_TARGET'] = 'source'
            elif not re.fullmatch(r'\d+\.\d+\.\d+', self.env.get('AGENT_VERSION', '')):
                raise ValueError('Set AGENT_REF=<40-hex SHA> or explicit AGENT_VERSION')
        self.project = self.env.get('SOAK_PROJECT', 'tracewick-soak')
        if not re.fullmatch('[a-z0-9][a-z0-9_-]*', self.project):
            raise ValueError('Invalid SOAK_PROJECT')
        self.env['TRACEWICK_IMAGE_TAG'] = self.project
        self.env['AGENT_IMAGE_TAG'] = self.project
        self.env.setdefault('RR_NUM_WORKERS', '1')
        if self.runtime == 'rr' and self.env['RR_NUM_WORKERS'] != '1':
            raise ValueError('Observed RR soak uses one persistent worker for diagnostic attribution')
        self.env.setdefault('WORK_STACK_DEPTH', '48')
        self.env.setdefault('PHP_FPM_MAX_CHILDREN', '1')
        self.env.setdefault('SWOOLE_WORKER_NUM', '1')
        self.rate = int(self.env.get('RATE', '10'))
        self.interval = float(self.env.get('STATS_INTERVAL', '15'))
        self.sample_rate = float(self.env.get('TRACEWICK_SAMPLE_RATE', '0.1'))
        if self.rate <= 0 or self.interval <= 0 or not 0 < self.sample_rate <= 1:
            raise ValueError('Positive RATE/STATS_INTERVAL and 0 < TRACEWICK_SAMPLE_RATE <= 1 required')
        self.env['TRACEWICK_SAMPLE_RATE'] = str(self.sample_rate)
        self.env.setdefault('EXCIMER_VERSION', '1.2.7')
        self.durations = {p: self.env.get(k, default) for p, k, default in (
            ('baseline', 'BASELINE_DURATION', '5m'), ('warmup', 'WARMUP_DURATION', '5m'),
            ('steady', 'DURATION', '72h'), ('cooldown', 'COOLDOWN_DURATION', '2m'))}
        for value in self.durations.values():
            seconds(value)
        if seconds(self.durations['steady']) < self.interval * 3:
            raise ValueError('Steady duration must cover at least three telemetry intervals')
        self.drain_timeout = seconds(self.env.get('DRAIN_TIMEOUT', '2m'))
        self.stall_timeout = seconds(self.env.get('DELIVERY_STALL_TIMEOUT', '2m'))
        self.delivery_progress = time.monotonic()
        self.delivered = 0
        self.app = {'rr': 'app-rr', 'fpm': 'app-fpm', 'swoole': 'app-swoole'}[self.runtime]
        self.reader_service = 'app-' + self.reader
        self.base_url = self.env.get('BASE_URL') or {
            'fpm': 'http://127.0.0.1:8080', 'rr': 'http://127.0.0.1:8082',
            'swoole': 'http://127.0.0.1:8083'}[self.runtime]
        self.k6_url = self.env.get('K6_API_URL', 'http://127.0.0.1:6565')
        self.agent_url = 'http://127.0.0.1:' + self.env.get('AGENT_METRICS_PORT', '9090') + '/metrics'
        self.pyroscope_url = 'http://127.0.0.1:' + self.env.get('PYROSCOPE_PORT', '4040')
        self.compose = shlex.split(self.env.get('COMPOSE', 'docker compose')) + ['-p', self.project]
        self.docker = Docker()
        self.shared_smoke = self.env.get('SOAK_SMOKE_SHARED_CGROUP') == '1'
        if self.shared_smoke and any(seconds(v) > 60 for v in self.durations.values()):
            raise ValueError('Shared-cgroup harness smoke is limited to 60 seconds per phase')
        self.directory = Path(self.env.get('REPORTS_DIR', 'reports/_local')).resolve() / (
            'soak-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
        self.directory.mkdir(parents=True, mode=0o755)
        self.harness = self.directory / 'harness'
        self.harness.mkdir()
        shutil.copyfile(ROOT / 'generators/k6/soak.js', self.harness / 'soak.js')
        self.spool_script = (ROOT / 'scripts/soak_spool.php').read_text()
        self.load_name = self.project + '-load'
        self.ids = {}
        self.guard = Continuity(self.interval)
        self.load = None
        self.last_k6 = {'requests': 0}
        self.phase = 'prepare'
        self.records = deque(maxlen=2)
        self.phases = []
        self.identity = {'parameters': {k: self.env.get(k) for k in (
            'TRACEWICK_VERSION', 'AGENT_VERSION', 'AGENT_REF', 'WORK_STACK_DEPTH',
            'RR_NUM_WORKERS', 'PHP_FPM_MAX_CHILDREN', 'SWOOLE_WORKER_NUM', 'EXCIMER_VERSION', 'EXCIMER_REF',
            'WORK_BUSY_MS', 'WORK_SLEEP_MS')}, 'rate': self.rate,
            'sample_rate': self.sample_rate, 'durations': self.durations,
            'stats_interval': self.interval, 'host': command(['uname', '-a']),
            'cpu_count': os.cpu_count(), 'clock_ticks': os.sysconf('SC_CLK_TCK'),
            'meminfo': Path('/proc/meminfo').read_text(),
            'repo_sha': command(['git', 'rev-parse', 'HEAD'], cwd=ROOT),
            'git_status': command(['git', 'status', '--porcelain'], cwd=ROOT),
            'harness_sha256': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in (
                'scripts/soak.py', 'scripts/soaklib.py', 'scripts/soak_probe.sh',
                'scripts/soak_spool.php', 'generators/k6/soak.js', 'compose.yaml')},
            'docker': {k: v for k, v in self.docker.get('/info').items() if k in (
                'ServerVersion', 'Architecture', 'CgroupVersion', 'Driver', 'NCPU', 'MemTotal')}}

    def compose_run(self, *args):
        subprocess.run(self.compose + list(args), env=self.env, cwd=ROOT, check=True)

    def cid(self, service):
        return command(self.compose + ['--profile', 'agent', 'ps', '-q', service], env=self.env, cwd=ROOT)

    def phase_start(self, name):
        self.phase = name
        record = {'phase': name, 'ts': time.time(), 'monotonic': time.monotonic()}
        self.phases.append(record)
        with (self.directory / 'phases.jsonl').open('a') as stream:
            stream.write(json.dumps(record) + '\n')
        print(f'==> {name}: {self.directory}', flush=True)

    def wait_ready(self, url):
        deadline = time.monotonic() + 120
        while True:
            try:
                with urllib.request.urlopen(url, timeout=3) as response:
                    if response.status == 200:
                        return
            except (OSError, urllib.error.URLError):
                pass
            if time.monotonic() >= deadline:
                raise RuntimeError(f'Not ready: {url}')
            time.sleep(1)

    def health(self, enabled):
        health = get_json(self.base_url + '/health')
        if not health.get('ok') or not health.get('excimer') or not health.get('tracewick'):
            raise ValueError('Health must confirm app, Tracewick and real Excimer')
        if health.get('profiling_enabled') is not enabled:
            raise ValueError('Wrong profiling state')
        if health.get('work_stack_depth') != int(self.env['WORK_STACK_DEPTH']):
            raise ValueError('Wrong workload depth')
        diagnostics = health.get('diagnostics')
        if enabled and diagnostics and diagnostics.get('inactiveSampler') is not None:
            raise ValueError('Inactive sampler despite enabled profiling')
        return health

    def take(self, generator=None):
        sample = {'ts': time.time(), 'monotonic': time.monotonic(), 'phase': self.phase,
                  'containers': {role: self.docker.sample(cid, processes=role in ('app', 'reader'), allow_shared=self.shared_smoke)
                                 for role, cid in self.ids.items()}}
        if generator:
            sample['containers']['generator'] = self.docker.sample(generator, allow_shared=self.shared_smoke)
            sample['k6'] = k6_metrics(self.k6_url)
            self.last_k6 = sample['k6']
        else:
            sample['k6'] = self.last_k6
        if self.reader == 'agent':
            sample['agent'] = agent_metrics(self.agent_url)
        if self.phase != 'baseline':
            sample['health'] = self.health(True)
        else:
            sample['health'] = self.health(False)
        probe = subprocess.run(['docker', 'exec', '-i', self.ids['app'], 'php'],
            input=self.spool_script, text=True,
            capture_output=True, timeout=15)
        if probe.returncode:
            raise RuntimeError('Spool probe failed: ' + probe.stderr.strip())
        sample['spool'] = json.loads(probe.stdout)
        with (self.directory / 'telemetry.jsonl').open('a') as stream:
            stream.write(json.dumps(sample) + '\n')
        self.records.append(sample)
        core = {**sample, 'containers': {k: v for k, v in sample['containers'].items() if k != 'generator'}}
        self.guard.check(core)
        if len(self.records) > 1 and self.phase != 'baseline':
            previous = self.records[-2]
            if sample.get('agent') and previous.get('agent'):
                for key in ('profiles_rejected_total', 'profiles_retried_total'):
                    if sample['agent'][key] > previous['agent'][key]:
                        raise ValueError('Delivery failures increased: ' + key)
            if self.runtime == 'rr' and previous['health'].get('diagnostics'):
                for key in ('droppedProfiles', 'skippedProfiles', 'failedProfiles', 'rejectedProfiles', 'swallowedErrors', 'samplerFailures'):
                    if sample['health']['diagnostics'][key] > previous['health']['diagnostics'][key]:
                        raise ValueError('Writer diagnostics increased: ' + key)
        now = time.monotonic()
        if sample.get('agent') and sample['agent']['profiles_delivered_total'] != self.delivered:
            self.delivered = sample['agent']['profiles_delivered_total']
            self.delivery_progress = now
        if sample['spool']['pending_files'] == 0:
            self.delivery_progress = now
        elif (sample['spool']['oldest_age_seconds'] > self.stall_timeout or
              (self.reader == 'agent' and now - self.delivery_progress > self.stall_timeout)):
            raise ValueError('Delivery stalled with pending spool work')
        if len(self.records) > 1 and sample['spool']['rejected_files'] > self.records[-2]['spool']['rejected_files']:
            raise ValueError('Rejected spool files increased')
        return sample

    def run_load(self, phase):
        self.phase_start(phase)
        self.last_k6 = {'requests': 0}
        duration = self.durations[phase]
        output = (self.directory / (phase + '-k6.log')).open('w')
        args = ['docker', 'run', '--name', self.load_name, '--network', 'host',
                '--user', f'{os.getuid()}:{os.getgid()}',
                '-v', str(self.harness) + ':/scripts:ro',
                '-v', str(self.directory) + ':/out', '-e', 'BASE_URL=' + self.base_url,
                '-e', 'RATE=' + str(self.rate), '-e', 'DURATION=' + duration,
                '-e', 'EXPECT_PROFILING=' + ('0' if phase == 'baseline' else '1'),
                self.env.get('K6_IMAGE', 'grafana/k6:1.8.2'), 'run',
                '--address=' + self.k6_url.removeprefix('http://'), '/scripts/soak.js',
                '--summary-export=/out/' + phase + '-k6.json']
        started = time.monotonic()
        self.load = subprocess.Popen(args, stdout=output, stderr=subprocess.STDOUT)
        try:
            generator = None
            while self.load.poll() is None:
                try:
                    generator = self.docker.inspect(self.load_name)['Id']
                    k6_metrics(self.k6_url)
                    break
                except (OSError, RuntimeError, ValueError, KeyError, urllib.error.URLError):
                    if time.monotonic() - started > 30:
                        raise RuntimeError('k6 REST telemetry did not become ready')
                    time.sleep(.2)
            if generator is None or self.load.poll() is not None:
                raise RuntimeError('k6 exited before telemetry became ready')
            while self.load.poll() is None:
                # Stop sampling before the normal generator exit can race a stats read.
                if time.monotonic() - started >= seconds(duration):
                    break
                if not self.docker.inspect(generator)['State']['Running']:
                    break
                self.take(generator)
                time.sleep(self.interval)
            code = self.load.wait(timeout=30)
            if code:
                raise RuntimeError(f'{phase}: k6 failed ({code}), see {phase}-k6.log')
            if time.monotonic() - started < seconds(duration):
                raise ValueError('Load ended before the requested duration')
            summary = json.loads((self.directory / (phase + '-k6.json')).read_text())
            metrics = summary['metrics']
            if metrics['http_reqs']['count'] <= 0 or metrics.get('dropped_iterations', {}).get('count', 0):
                raise ValueError('No requests or dropped load-generator iterations')
        finally:
            subprocess.run(['docker', 'rm', '-f', self.load_name], capture_output=True, timeout=30)
            self.load.wait(timeout=30)
            self.load = None
            output.close()

    def runtime_identity(self):
        script = ('require "vendor/autoload.php"; echo json_encode(['
                  '"php"=>PHP_VERSION,"excimer"=>phpversion("excimer"),'
                  '"version"=>Composer\\InstalledVersions::getPrettyVersion("tracewick/tracewick"),'
                  '"reference"=>Composer\\InstalledVersions::getReference("tracewick/tracewick")]);')
        actual = json.loads(command(['docker', 'exec', self.ids['app'], 'php', '-r', script]))
        if '#' in self.package:
            if actual['reference'] != self.package.split('#')[1]:
                raise ValueError('Installed core reference does not match requested SHA')
        elif actual['version'].lstrip('v') != self.package.lstrip('v'):
            raise ValueError('Installed core version does not match requested version')
        if self.reader == 'agent':
            actual['agent_version'] = command(['docker', 'exec', self.ids['reader'], 'tracewick-agent', 'version'])
            if self.env.get('AGENT_REF'):
                actual['agent_reference'] = command(['docker', 'exec', self.ids['reader'], 'cat', '/agent-reference'])
                if actual['agent_reference'] != self.env['AGENT_REF']:
                    raise ValueError('Agent build reference mismatch')
            elif self.env['AGENT_VERSION'] != actual['agent_version']:
                raise ValueError('Installed agent version mismatch')
        actual['containers'] = {}
        for role, cid in self.ids.items():
            info = self.docker.inspect(cid)
            actual['containers'][role] = {'id': info['Id'], 'image_id': info['Image'],
                'image': info['Config']['Image'], 'command': info['Config']['Cmd'],
                'started_at': info['State']['StartedAt'],
                'limits': {k: info['HostConfig'].get(k) for k in ('Memory', 'NanoCpus', 'CpuQuota', 'CpuPeriod', 'RestartPolicy')}}
        self.identity.setdefault('runtimes', []).append(actual)
        (self.directory / 'identity.json').write_text(json.dumps(self.identity, indent=2) + '\n')

    def read_records(self):
        path = self.directory / 'telemetry.jsonl'
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def drain(self):
        deadline = time.monotonic() + self.drain_timeout
        while True:
            snapshot = self.take()
            if snapshot['spool']['pending_files'] == 0 and snapshot.get('agent', {}).get('inflight_uploads', 0) == 0:
                return snapshot['spool']
            if time.monotonic() >= deadline:
                raise ValueError('Spool did not drain within DRAIN_TIMEOUT')
            time.sleep(self.interval)

    def run(self):
        result = {'status': 'invalid', 'error': None}
        try:
            existing = command(self.compose + ['--profile', 'agent', 'ps', '-aq'], env=self.env, cwd=ROOT)
            if existing:
                raise ValueError(f'Project {self.project} already exists; inspect/clean it or choose SOAK_PROJECT')
            # Never silently send a second generator to an existing k6 REST endpoint.
            try:
                get_json(self.k6_url + '/v1/status')
            except OSError:
                pass
            else:
                raise ValueError('k6 REST port already in use')
            self.compose_run('--profile', 'agent', 'build', self.app, self.reader_service,
                             *(['app-nginx'] if self.runtime == 'fpm' else []))
            self.compose_run('up', '-d', '--no-deps', 'pyroscope')
            self.wait_ready(self.pyroscope_url + '/ready')
            self.env['TRACEWICK_ENABLED'] = '0'
            self.compose_run('up', '-d', '--no-deps', self.app,
                             *(['app-nginx'] if self.runtime == 'fpm' else []))
            self.wait_ready(self.base_url + '/health')
            app = self.cid(self.app)
            probe = subprocess.run(['docker', 'exec', '-i', app, 'php'], input=self.spool_script,
                                   text=True, capture_output=True, check=True, timeout=15)
            initial_spool = json.loads(probe.stdout)
            if initial_spool['pending_files'] or initial_spool['rejected_files']:
                raise ValueError('Spool is not empty before the run; refusing to consume prior evidence')
            self.compose_run('--profile', 'agent', 'up', '-d', '--no-deps', self.reader_service)
            self.ids = {'app': app, 'reader': self.cid(self.reader_service),
                        'pyroscope': self.cid('pyroscope')}
            self.runtime_identity()
            self.health(False)
            self.run_load('baseline')
            self.env['TRACEWICK_ENABLED'] = '1'
            self.compose_run('up', '-d', '--no-deps', '--force-recreate', self.app)
            self.wait_ready(self.base_url + '/health')
            self.ids['app'] = self.cid(self.app)
            self.guard = Continuity(self.interval)  # Baseline recreation is intentional and recorded.
            self.runtime_identity()
            self.run_load('warmup')
            warmup = [r for r in self.read_records() if r['phase'] == 'warmup']
            if self.reader == 'agent' and (len(warmup) < 2 or warmup[-1]['agent']['profiles_delivered_total'] <= warmup[0]['agent']['profiles_delivered_total']):
                raise ValueError('Warmup did not demonstrate delivery; refusing to start steady load')
            self.phase_start('preflight-drain')
            self.drain()
            self.run_load('steady')
            self.phase_start('drain')
            result['drain'] = self.drain()
            self.phase_start('cooldown')
            deadline = time.monotonic() + seconds(self.durations['cooldown'])
            while time.monotonic() < deadline:
                cooldown = self.take()
                if self.runtime != 'swoole' and cooldown['spool']['pending_files']:
                    raise ValueError('New pending spool files after drain')
                time.sleep(self.interval)
            self.records = self.read_records()
            steady = [r for r in self.records if r['phase'] == 'steady']
            if len(steady) < 3 or steady[-1]['monotonic'] - steady[0]['monotonic'] < seconds(self.durations['steady']) - 2 * self.interval - 5:
                raise ValueError('Insufficient coverage of the requested steady window')
            if self.reader == 'agent':
                if steady[-1]['agent']['profiles_delivered_total'] <= steady[0]['agent']['profiles_delivered_total']:
                    raise ValueError('No delivered profiles during steady window')
                for key in ('profiles_rejected_total', 'profiles_retried_total'):
                    if steady[-1]['agent'][key] > steady[0]['agent'][key]:
                        raise ValueError(f'Delivery failures during steady window: {key}')
            if self.runtime == 'rr':
                first = steady[0]['health']['diagnostics']
                last = steady[-1]['health']['diagnostics']
                for key in ('droppedProfiles', 'skippedProfiles', 'failedProfiles', 'rejectedProfiles', 'swallowedErrors', 'samplerFailures'):
                    if last[key] > first[key]:
                        raise ValueError('Writer diagnostics increased: ' + key)
                if last['collectedProfiles'] <= first['collectedProfiles']:
                    raise ValueError('No profiles collected by the writer')
            result['summary'] = summarize(self.records)
            result['baseline_summary'] = summarize([{**r, 'phase': 'steady'} for r in self.records if r['phase'] == 'baseline'])
            hours = []
            for offset in range(0, int(seconds(self.durations['steady'])), 3600):
                rows = [s for s in steady if offset <= s['monotonic'] - steady[0]['monotonic'] < offset + 3600]
                if len(rows) >= 2:
                    hours.append({'hour': offset // 3600, **summarize(rows)})
            (self.directory / 'hourly.json').write_text(json.dumps(hours, indent=2) + '\n')
            result['status'] = ('harness smoke only; shared cgroup statistics' if self.shared_smoke
                                else 'valid observation; inspect resource trends')
        except (Exception, KeyboardInterrupt) as error:
            result['error'] = str(error) or type(error).__name__
            print('INVALID: ' + result['error'], file=sys.stderr, flush=True)
        finally:
            if self.load is not None:
                subprocess.run(['docker', 'rm', '-f', self.load_name], capture_output=True, timeout=30)
            result['phases'] = self.phases
            result['shared_cgroup_smoke'] = self.shared_smoke
            try:
                export_csv(self.directory, self.read_records())
            except Exception as error:
                result['status'] = 'invalid'
                result['error'] = 'Telemetry artifact export failed: ' + str(error)
            write_report(self.directory, result)
            print('Report: ' + str(self.directory / 'soak-report.md'), flush=True)
        return 0 if result['status'] != 'invalid' else 1


def main():
    def interrupted(*_):
        raise KeyboardInterrupt()
    signal.signal(signal.SIGTERM, interrupted)
    try:
        return Soak().run()
    except (Exception, KeyboardInterrupt) as error:
        print('soak: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
