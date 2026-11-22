#!/usr/bin/env python3
"""Observe healthy traffic through explicit backend and reader failure epochs."""
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from soak import Soak
from soaklib import Continuity, agent_metrics, command, export_csv, k6_metrics


class Recovery(Soak):
    def __init__(self):
        super().__init__()
        self.started = None
        self.actions = set()
        self.reader_running = True
        self.reader_epoch = 0
        self.reader_signature = None
        self.previous_metrics = None
        self.paused = False
        self.backend_running = True
        self.app_guard = Continuity(self.interval)
        self.events = []

    def event(self, name, **details):
        record = {'event': name, 'ts': time.time(), 'monotonic': time.monotonic(), **details}
        self.events.append(record)
        with (self.directory / 'events.jsonl').open('a') as stream:
            stream.write(json.dumps(record) + '\n')
        print('RECOVERY EVENT ' + name, flush=True)

    def restart_reader(self):
        command(['docker', 'start', self.ids['reader']])
        self.wait_ready(self.agent_url)
        self.reader_running = True
        self.reader_epoch += 1
        self.reader_signature = None
        self.previous_metrics = None

    def inject(self):
        elapsed = time.monotonic() - self.started
        for at, name in ((300, 'backend-stop'), (600, 'backend-start'),
                         (900, 'reader-stop'), (960, 'reader-start'),
                         (1200, 'reader-inflight-kill'), (1260, 'reader-recover')):
            if elapsed < at or name in self.actions:
                continue
            self.actions.add(name)
            if name == 'backend-stop':
                command(['docker', 'stop', self.ids['pyroscope']])
                self.backend_running = False
            elif name == 'backend-start':
                command(['docker', 'start', self.ids['pyroscope']])
                self.backend_running = True
            elif name == 'reader-stop':
                self.event('reader-before-stop', metrics=agent_metrics(self.agent_url))
                command(['docker', 'stop', self.ids['reader']])
                self.reader_running = False
            elif name == 'reader-start':
                self.restart_reader()
            elif name == 'reader-inflight-kill':
                command(['docker', 'pause', self.ids['pyroscope']])
                self.paused = True
                deadline = time.monotonic() + 12
                while True:
                    metrics = agent_metrics(self.agent_url)
                    if metrics['inflight_uploads'] > 0:
                        break
                    if time.monotonic() >= deadline:
                        raise ValueError('Could not establish an inflight upload before reader kill')
                    time.sleep(.1)
                self.event('reader-before-kill', metrics=metrics)
                command(['docker', 'kill', '--signal=KILL', self.ids['reader']])
                self.reader_running = False
                script = ('$names=[];foreach(new RecursiveIteratorIterator(new RecursiveDirectoryIterator('
                          'getenv("TRACEWICK_SPOOL_DIR"),FilesystemIterator::SKIP_DOTS)) as $f){'
                          'if($f->isFile()&&str_contains($f->getFilename(),".claimed-"))'
                          '{$names[]=$f->getFilename();}}echo json_encode($names);')
                claims = json.loads(command(['docker', 'exec', self.ids['app'], 'php', '-r', script]))
                if not claims:
                    raise ValueError('Reader kill did not leave a claimed spool file')
                self.event('orphaned-claims', filenames=claims)
            elif name == 'reader-recover':
                command(['docker', 'unpause', self.ids['pyroscope']])
                self.paused = False
                self.restart_reader()
            self.event(name)

    def take(self, generator=None):
        if self.started is None:
            self.started = time.monotonic()
        if generator:
            self.inject()
        sample = {'ts': time.time(), 'monotonic': time.monotonic(), 'phase': self.phase,
                  'reader_epoch': self.reader_epoch, 'reader_running': self.reader_running,
                  'backend_running': self.backend_running, 'backend_paused': self.paused,
                  'containers': {'app': self.docker.sample(self.ids['app'], processes=True)},
                  'health': self.health(True)}
        self.app_guard.check({'monotonic': sample['monotonic'],
                              'containers': {'app': sample['containers']['app']}})
        if self.reader_running:
            reader = self.docker.sample(self.ids['reader'], processes=True)
            signature = (reader['id'], reader['started_at'], reader['restarts'],
                         tuple((p['pid'], p['start_ticks']) for p in reader['processes']))
            if self.reader_signature is not None and self.reader_signature != signature:
                raise ValueError('Unexpected reader replacement within an epoch')
            self.reader_signature = signature
            sample['containers']['reader'] = reader
            sample['agent'] = agent_metrics(self.agent_url)
            if self.previous_metrics is not None:
                for name in ('profiles_delivered_total', 'profiles_retried_total', 'profiles_rejected_total'):
                    if sample['agent'][name] < self.previous_metrics[name]:
                        raise ValueError('Unexpected reader counter reset')
            self.previous_metrics = sample['agent']
            if sample['agent']['profiles_rejected_total']:
                raise ValueError('Reader rejected profiles')
        else:
            sample['agent'] = None
        if self.backend_running:
            sample['containers']['pyroscope'] = self.docker.sample(self.ids['pyroscope'])
        if generator:
            sample['containers']['generator'] = self.docker.sample(generator)
            sample['k6'] = k6_metrics(self.k6_url)
            self.last_k6 = sample['k6']
        else:
            sample['k6'] = self.last_k6
        probe = subprocess.run(['docker', 'exec', '-i', self.ids['app'], 'php'],
                               input=self.spool_script, text=True, capture_output=True,
                               check=True, timeout=15)
        sample['spool'] = json.loads(probe.stdout)
        if sample['spool']['rejected_files']:
            raise ValueError('Rejected spool files found')
        for name in ('droppedProfiles', 'skippedProfiles', 'failedProfiles', 'rejectedProfiles',
                     'swallowedErrors', 'samplerFailures'):
            if sample['health']['diagnostics'][name]:
                raise ValueError('Writer diagnostic failure: ' + name)
        with (self.directory / 'telemetry.jsonl').open('a') as stream:
            stream.write(json.dumps(sample) + '\n')
        self.records.append(sample)
        return sample

    def execute(self):
        self.env['TRACEWICK_ENABLED'] = '1'
        self.compose_run('up', '-d', '--no-deps', '--force-recreate', self.app)
        self.wait_ready(self.base_url + '/health')
        self.compose_run('--profile', 'agent', 'up', '-d', '--no-deps', '--force-recreate', self.reader_service)
        self.wait_ready(self.agent_url)
        self.ids = {'app': self.cid(self.app), 'reader': self.cid(self.reader_service),
                    'pyroscope': self.cid('pyroscope')}
        # Explicit starts delimit recovery epochs after SIGTERM and SIGKILL.
        command(['docker', 'update', '--restart=no', self.ids['reader']])
        self.runtime_identity()
        self.durations['steady'] = '35m'
        self.drain_timeout = 12 * 60
        self.run_load('steady')
        if len(self.actions) != 6:
            raise ValueError('Not all declared failure actions executed')
        self.phase_start('drain')
        final = self.drain()
        records = self.read_records()
        down = [r for r in records if not r['backend_running']]
        if not down or max(r['spool']['pending_files'] for r in down) < 50:
            raise ValueError('Backend outage did not demonstrate a material backlog')
        if not any(r['agent'] and r['agent']['profiles_retried_total'] > 0 for r in down):
            raise ValueError('Backend outage did not exercise delivery retries')
        if records[-1]['agent']['profiles_delivered_total'] <= 0:
            raise ValueError('No delivery after reader recovery')
        export_csv(self.directory, records)
        return {'status': 'passed', 'drain': final, 'actions': sorted(self.actions),
                'reader_epochs': self.reader_epoch + 1,
                'max_pending': max(r['spool']['pending_files'] for r in records),
                'max_pending_age_seconds': max(r['spool']['oldest_age_seconds'] for r in records)}


def main():
    runner = Recovery()
    result = {'status': 'failed'}
    try:
        result = runner.execute()
    except Exception as error:
        result['error'] = str(error)
        raise
    finally:
        if runner.paused:
            subprocess.run(['docker', 'unpause', runner.ids['pyroscope']], check=True)
        (runner.directory / 'recovery.json').write_text(json.dumps(result, indent=2) + '\n')
        print('Recovery result: ' + str(runner.directory), flush=True)


if __name__ == '__main__':
    main()
