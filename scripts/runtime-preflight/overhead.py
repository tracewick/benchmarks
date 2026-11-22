#!/usr/bin/env python3
"""Paired, equally warmed RR overhead observations using the soak collector."""
import argparse
import json
import os
import sys
import time
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from soak import Soak
from soaklib import command, export_csv, summarize


class Overhead(Soak):
    def health(self, enabled):
        return super().health(self.enabled)

    def measure(self, enabled, settle, duration):
        self.enabled = enabled
        self.env['TRACEWICK_ENABLED'] = '1' if enabled else '0'
        self.compose_run('up', '-d', '--no-deps', '--force-recreate', self.app)
        self.wait_ready(self.base_url + '/health')
        self.compose_run('--profile', 'agent', 'up', '-d', '--no-deps', self.reader_service)
        self.wait_ready(self.agent_url)
        self.ids = {'app': self.cid(self.app), 'reader': self.cid(self.reader_service),
                    'pyroscope': self.cid('pyroscope')}
        self.runtime_identity()
        phase = 'steady' if enabled else 'baseline'
        self.durations[phase] = settle
        self.run_load(phase)
        for name in ('telemetry.jsonl', 'phases.jsonl', phase + '-k6.json', phase + '-k6.log'):
            (self.directory / name).rename(self.directory / ('settle-' + name))
        self.phases = []
        self.records = deque(maxlen=2)
        self.durations[phase] = duration
        self.run_load(phase)
        self.phase_start('drain')
        final = self.drain()
        records = self.read_records()
        measured = [r for r in records if r['phase'] == phase]
        result = {'status': 'passed', 'enabled': enabled, 'settle': settle, 'duration': duration,
                  'summary': summarize([{**r, 'phase': 'steady'} for r in measured]),
                  'drain': final}
        if enabled:
            if measured[-1]['agent']['profiles_delivered_total'] <= measured[0]['agent']['profiles_delivered_total']:
                raise ValueError('No delivery during profiled measurement')
        elif any(r['spool']['pending_files'] for r in measured):
            raise ValueError('Disabled profiling produced pending work')
        export_csv(self.directory, records)
        (self.directory / 'measurement.json').write_text(json.dumps(result, indent=2) + '\n')
        return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--smoke', action='store_true')
    args = parser.parse_args()
    project = os.environ.get('SOAK_PROJECT', 'runtime-preflight')
    existing = command(['docker', 'compose', '-p', project, '--profile', 'agent', 'ps', '-aq'], cwd=ROOT)
    if existing:
        raise ValueError('Project already exists, inspect it before starting a new campaign')
    settle = '15s' if args.smoke else '2m'
    duration = '30s' if args.smoke else '10m'
    order = [False, True] if args.smoke else [False, True, True, False, False, True]
    parent = Path(os.environ['REPORTS_DIR']).resolve()
    parent.mkdir(parents=True, exist_ok=True)
    index = []
    for number, enabled in enumerate(order, 1):
        observer = Overhead()
        image_tag = os.environ.get('PREFLIGHT_IMAGE_TAG', observer.project)
        observer.env['TRACEWICK_IMAGE_TAG'] = image_tag
        observer.env['AGENT_IMAGE_TAG'] = image_tag
        entry = {'number': number, 'enabled': enabled, 'directory': str(observer.directory),
                 'started_at': time.time(), 'status': 'running'}
        index.append(entry)
        (parent / 'overhead-index.json').write_text(json.dumps(index, indent=2) + '\n')
        try:
            if number == 1:
                observer.compose_run('up', '-d', '--no-deps', 'pyroscope')
                observer.wait_ready(observer.pyroscope_url + '/ready')
            print(f'PAIR PHASE {number}/{len(order)} enabled={enabled}', flush=True)
            result = observer.measure(enabled, settle, duration)
            entry['status'] = result['status']
            entry['ended_at'] = time.time()
        except Exception as error:
            entry['status'] = 'failed'
            entry['error'] = str(error)
            (observer.directory / 'measurement.json').write_text(json.dumps(entry, indent=2) + '\n')
            raise
        finally:
            (parent / 'overhead-index.json').write_text(json.dumps(index, indent=2) + '\n')
    print('OVERHEAD CAMPAIGN PASSED', flush=True)


if __name__ == '__main__':
    main()
