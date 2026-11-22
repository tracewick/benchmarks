#!/usr/bin/env python3
"""Read the synthetic work back from Pyroscope after agent acknowledgement."""
import argparse
import json
import time
import urllib.request
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('output', type=Path)
parser.add_argument('--selector', default='{service_name="symfony-preflight"}')
args = parser.parse_args()

def query(method, body):
    request = urllib.request.Request(
        'http://127.0.0.1:4040/querier.v1.QuerierService/' + method,
        json.dumps(body).encode(), {'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)

deadline = time.monotonic() + 90
while True:
    now = int(time.time() * 1000)
    types = query('ProfileTypes', {'start': now - 3600000, 'end': now + 60000})
    wall = [t.get('ID', t.get('id')) for t in types.get('profileTypes', []) if t.get('name') == 'wall']
    if wall:
        result = query('SelectMergeStacktraces', {
            'profileTypeID': wall[0], 'labelSelector': args.selector,
            'start': now - 3600000, 'end': now + 60000})
        args.output.write_text(json.dumps(result, indent=2) + '\n')
        graph = result.get('flamegraph', {})
        if int(graph.get('total', 0)) > 0 and any('busyWork' in name for name in graph.get('names', [])):
            print('Synthetic busyWork observed in Pyroscope', graph['total'])
            break
    if time.monotonic() >= deadline:
        raise RuntimeError('Synthetic workload was not visible in Pyroscope before deadline')
    time.sleep(1)
