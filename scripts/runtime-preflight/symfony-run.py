#!/usr/bin/env python3
"""Observe one real Symfony fixture process and require end-to-end delivery."""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from soaklib import Continuity, Docker, agent_metrics

parser = argparse.ArgumentParser()
parser.add_argument('mode', choices=('http', 'messenger'))
parser.add_argument('evidence', type=Path)
parser.add_argument('--seconds', type=int, default=1200)
args = parser.parse_args()
directory = args.evidence.resolve()
directory.mkdir(parents=True, exist_ok=True)
engine = Docker()
reader = engine.inspect('runtime-preflight-symfony-reader')['Id']
backend = engine.inspect('runtime-preflight-pyroscope-1')['Id']
metrics_url = 'http://127.0.0.1:9091/metrics'
before = agent_metrics(metrics_url)
name = 'symfony-preflight-' + args.mode
image = 'tracewick-symfony-preflight:20261122'
fixtures = Path(__file__).resolve().parent
mounts = ['-v', str(fixtures) + ':/fixtures:ro',
          '-v', str(directory) + ':/evidence',
          '-v', 'runtime-preflight-symfony-spool:/var/spool/tracewick']
output = (directory / (args.mode + '.log')).open('w')
process = subprocess.Popen(['docker', 'run', '--name', name, '--user', '33:33',
                            *mounts, image, '/fixtures/symfony.php', args.mode, str(args.seconds)],
                           stdout=output, stderr=subprocess.STDOUT)
guard = Continuity(15)
started = time.monotonic()
cid = None
try:
    while process.poll() is None:
        try:
            cid = engine.inspect(name)['Id']
            break
        except RuntimeError:
            time.sleep(.1)
    if cid is None:
        raise RuntimeError('Symfony fixture exited before telemetry started')
    while process.poll() is None and time.monotonic() - started < args.seconds - 5:
        if not engine.inspect(cid)['State']['Running']:
            break
        sample = {'ts': time.time(), 'monotonic': time.monotonic(), 'phase': args.mode,
                  'containers': {'app': engine.sample(cid, processes=True),
                                 'reader': engine.sample(reader, processes=True),
                                 'pyroscope': engine.sample(backend)},
                  'agent': agent_metrics(metrics_url)}
        guard.check(sample)
        if sample['agent']['profiles_rejected_total'] or sample['agent']['profiles_retried_total']:
            raise ValueError('Unexpected delivery failure during Symfony healthy workload')
        with (directory / (args.mode + '-telemetry.jsonl')).open('a') as stream:
            stream.write(json.dumps(sample) + '\n')
        time.sleep(15)
    code = process.wait(timeout=90)
    if code:
        raise RuntimeError(f'Symfony {args.mode} failed with exit {code}; see its log')
    result = json.loads((directory / args.mode / 'result.json').read_text())
    assert result['status'] == 'passed'
    deadline = time.monotonic() + 180
    spool_script = (ROOT / 'scripts/soak_spool.php').read_text()
    while True:
        probe = subprocess.run(['docker', 'run', '--rm', '-i', '--user', '33:33',
                                '-v', 'runtime-preflight-symfony-spool:/var/spool/tracewick', image],
                               input=spool_script, text=True, capture_output=True, check=True, timeout=20)
        spool = json.loads(probe.stdout)
        after = agent_metrics(metrics_url)
        delta = after['profiles_delivered_total'] - before['profiles_delivered_total']
        if spool['pending_files'] == 0 and after['inflight_uploads'] == 0 and delta == result['diagnostics']['deliveredProfiles']:
            break
        if time.monotonic() >= deadline:
            raise ValueError('Symfony writer/delivery counts did not reconcile after drain')
        time.sleep(1)
    selector = '{service_name="symfony-preflight",route="preflight_work"}'
    if args.mode == 'messenger':
        selector = '{service_name="symfony-preflight",message=' + json.dumps('TracewickBench\\Preflight\\WorkMessage') + '}'
    subprocess.run([sys.executable, str(fixtures / 'backend-query.py'),
                    str(directory / (args.mode + '-querier.json')), '--selector', selector], check=True)
    result['delivered_in_reader'] = delta
    result['final_spool'] = spool
    (directory / (args.mode + '-delivery.json')).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result), flush=True)
finally:
    if process.poll() is None:
        subprocess.run(['docker', 'stop', name], check=True, timeout=40)
        process.wait(timeout=30)
    output.close()
