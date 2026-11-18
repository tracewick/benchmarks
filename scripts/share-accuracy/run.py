#!/usr/bin/env python3
"""Serial, isolated known-function-share experiment. Not a load/overhead run."""
import argparse
import copy
import datetime
import hashlib
import importlib.util
import json
import os
import pathlib
import platform
import random
import socket
import subprocess
import time
import urllib.error
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
BENCH = HERE.parents[1]
WORKSPACE = BENCH.parent
spec = importlib.util.spec_from_file_location('share_analysis', HERE / 'analyze.py')
analysis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis)
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def command(args, **kwargs):
    return subprocess.check_output(args, text=True, **kwargs).strip()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def query(base, method, body):
    req = urllib.request.Request(base + '/querier.v1.QuerierService/' + method,
                                 json.dumps(body).encode(), {'Content-Type': 'application/json'})
    with OPENER.open(req, timeout=15) as response:
        return json.load(response)


def matrix(run_id):
    cases = []
    for hz in (100, 1000):
        for name, share, sleep in [('busy-70', 70, False), ('busy-20', 20, False), ('mixed-70', 70, True)]:
            for repeat in range(1, 4):
                key = f'{name}-{hz}hz-r{repeat}'
                cases.append({'id': key, 'application': f'share-{run_id}-{key}',
                              'seed': 83000 + len(cases), 'period_ns': 1_000_000_000 // hz,
                              'duration_ns': (40 if hz == 100 else 12) * 1_000_000_000,
                              'min_periods': 3000 if hz == 100 else 9000,
                              'alpha_percent': share, 'sleep_beta': sleep})
    random.Random(411).shuffle(cases)
    return cases


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--php-image', default='tracewick-uow-php:8.5')
    parser.add_argument('--pyroscope-image', default='grafana/pyroscope:2.4.3')
    parser.add_argument('--port', type=int, default=14040)
    args = parser.parse_args()
    with socket.socket() as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probe.bind(('127.0.0.1', args.port))
    run_id = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out = BENCH / 'reports' / '_local' / ('share-' + run_id)
    out.mkdir(parents=True)
    revisions = {}
    for name in ('tracewick', 'agent'):
        repo = WORKSPACE / name
        if command(['git', 'status', '--porcelain'], cwd=repo):
            raise RuntimeError(f'{name} must have a clean source tree')
        revisions[name] = command(['git', 'rev-parse', 'HEAD'], cwd=repo)
    revisions['benchmarks_base'] = command(['git', 'rev-parse', 'HEAD'], cwd=BENCH)
    image_ids = {key: command(['docker', 'image', 'inspect', value, '--format', '{{.Id}}'])
                 for key, value in [('php', args.php_image), ('pyroscope', args.pyroscope_image)]}
    manifest = {'revisions': revisions, 'images': vars(args), 'image_ids': image_ids,
                'host': {'platform': platform.platform(), 'cpus_visible': os.cpu_count()},
                'files_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in HERE.glob('*') if p.is_file()},
                'matrix': matrix(run_id), 'run_id': run_id,
                'thresholds': {'max_error_pp': analysis.MAX_ERROR_PP,
                               'max_other_percent': analysis.MAX_OTHER_PERCENT}}
    write(out / 'manifest.json', manifest)
    agent = out / 'tracewick-agent'
    subprocess.run(['go', 'build', '-o', str(agent), './cmd/tracewick-agent'],
                   cwd=WORKSPACE / 'agent', check=True)
    name = 'share-pyroscope-' + run_id.lower()
    base = 'http://127.0.0.1:' + str(args.port)
    results = []
    try:
        subprocess.run(['docker', 'run', '-d', '--name', name, '-p', f'127.0.0.1:{args.port}:4040',
                        '-e', 'HTTP_PROXY=', '-e', 'HTTPS_PROXY=', '-e', 'ALL_PROXY=', '-e', 'NO_PROXY=*',
                        args.pyroscope_image, '-server.http-listen-port=4040',
                        '-metastore.min-ready-duration=0', '-ingester.min-ready-duration=0',
                        '-segment-writer.min-ready-duration=0'], check=True, stdout=subprocess.DEVNULL)
        deadline = time.monotonic() + 90
        while True:
            try:
                with OPENER.open(base + '/ready', timeout=2) as response:
                    if response.status == 200:
                        break
            except (OSError, urllib.error.HTTPError):
                if time.monotonic() >= deadline:
                    raise
            time.sleep(1)
        for i, case in enumerate(manifest['matrix'], 1):
            directory = out / case['id']
            directory.mkdir()
            write(directory / 'spec.json', case)
            with (directory / 'capture.log').open('w') as log:
                subprocess.run(['docker', 'run', '--rm', '--user', f'{os.getuid()}:{os.getgid()}',
                                '-v', f'{WORKSPACE}:/workspace', '-w', '/workspace/benchmarks', args.php_image,
                                'php', '/workspace/benchmarks/scripts/share-accuracy/capture.php',
                                str(directory / 'spec.json'), str(directory)],
                               check=True, stdout=log, stderr=subprocess.STDOUT, timeout=120)
            oracle = json.loads((directory / 'oracle.json').read_text())
            with (directory / 'agent.log').open('w') as log:
                subprocess.run([str(agent), 'run', '--once', '--spool-dir=' + str(directory / 'spool'),
                                '--pyroscope-url=' + base, '--reader-id=share-check'],
                               check=True, stdout=log, stderr=subprocess.STDOUT, timeout=90)
            if list((directory / 'spool').rglob('*.spool')) or list((directory / 'spool').rglob('*.claimed-*')):
                raise RuntimeError('Unacknowledged spool remains')
            deadline = time.monotonic() + 300
            while True:
                now = int(time.time() * 1000)
                types = query(base, 'ProfileTypes', {'start': now - 3600000, 'end': now + 60000})
                write(directory / 'profile-types.json', types)
                ids = [t.get('ID', t.get('id')) for t in types.get('profileTypes', [])
                       if t.get('name') == 'wall' and t.get('sampleUnit') == 'nanoseconds']
                if ids:
                    response = query(base, 'SelectMergeStacktraces', {
                        'profileTypeID': ids[0], 'labelSelector': '{service_name="' + case['application'] + '"}',
                        'start': now - 3600000, 'end': now + 60000})
                    write(directory / 'querier.json', response)
                    if int(response.get('flamegraph', {}).get('total', 0)) > 0:
                        break
                if time.monotonic() >= deadline:
                    raise RuntimeError('No live backend profile')
                time.sleep(1)
            weights = analysis.phase_weights(response)
            result = analysis.assess(oracle, weights)
            # A deliberate label swap preserves total signal but must fail share validation.
            swapped = copy.deepcopy(weights)
            swapped['alpha'], swapped['beta'] = weights['beta'], weights['alpha']
            negative = analysis.assess(oracle, swapped)
            if 'share_error' not in negative['failures']:
                raise RuntimeError('Swapped-symbol negative control did not fail')
            result.update({'id': case['id'], 'negative_control': negative})
            write(directory / 'result.json', result)
            results.append(result)
            write(out / 'summary.json', {'complete': len(results) == len(manifest['matrix']),
                                        'pass': len(results) == len(manifest['matrix']) and all(r['pass'] for r in results),
                                        'results': results})
            print(f"{i}/18 {case['id']}: error={max(result['error_pp'].values()):.3f}pp "
                  f"other={result['other_percent']:.3f}% periods={result['weighted_periods']:.0f} "
                  f"{'PASS' if result['pass'] else 'FAIL'}", flush=True)
        if not all(r['pass'] for r in results):
            raise SystemExit('Share accuracy gate failed; all runs retained at ' + str(out))
        print('PASS: all 18 predeclared runs; artifacts: ' + str(out), flush=True)
    finally:
        exists = subprocess.run(['docker', 'inspect', name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if exists.returncode == 0:
            (out / 'pyroscope.log').write_text(command(['docker', 'logs', name], stderr=subprocess.STDOUT))
            subprocess.run(['docker', 'rm', '-f', name], check=True, stdout=subprocess.DEVNULL)


if __name__ == '__main__':
    main()
