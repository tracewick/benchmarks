#!/usr/bin/env python3
"""Correctness probe; fixed /workspace layout, see README.md. No capacity claims."""
import gzip
import http.server
import json
import pathlib
import socket
import struct
import subprocess
import threading
import time
import urllib.request

ROOT = pathlib.Path('/workspace/signal-verification/output')
SCRIPTS = '/workspace/benchmarks/scripts/signal-weight'
RUN = str(time.time_ns())
PUSHES = []


def varint(data, offset):
    value = shift = 0
    while True:
        byte = data[offset]
        offset += 1
        value |= (byte & 127) << shift
        if byte < 128:
            return value, offset
        shift += 7


def fields(data):
    offset = 0
    while offset < len(data):
        tag, offset = varint(data, offset)
        wire = tag & 7
        if wire == 0:
            value, offset = varint(data, offset)
        elif wire == 2:
            size, offset = varint(data, offset)
            value, offset = data[offset:offset + size], offset + size
        else:
            raise AssertionError(f'Unsupported wire {wire}')
        yield tag >> 3, value


def values(data):
    if data[:2] == b'\x1f\x8b':
        data = gzip.decompress(data)
    result = []
    for number, sample in fields(data):
        if number == 2:
            for field, value in fields(sample):
                if field == 2:
                    if isinstance(value, int):
                        result.append(value)
                    else:
                        offset = 0
                        while offset < len(value):
                            item, offset = varint(value, offset)
                            result.append(item)
    return result


class Proxy(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers['Content-Length']))
        decoded = gzip.decompress(body) if self.headers.get('Content-Encoding') == 'gzip' else body
        profiles = []
        for number, series in fields(decoded):
            if number == 1:
                for field, sample in fields(series):
                    if field == 2:
                        profiles.extend(value for key, value in fields(sample) if key == 1)
        request = urllib.request.Request('http://127.0.0.1:4040' + self.path, body,
                                         {k: v for k, v in self.headers.items() if k.lower() not in ('host', 'content-length')})
        with urllib.request.urlopen(request, timeout=30) as response:
            reply = response.read()
            status = response.status
        for profile in profiles:
            path = ROOT / f'push-{RUN}-{len(PUSHES)}.pprof'
            path.write_bytes(profile)
            PUSHES.append({'file': str(path), 'values': values(profile)})
        self.send_response(status)
        self.end_headers()
        self.wfile.write(reply)

    def log_message(self, *_):
        pass


def php(*args):
    cmd = ['docker', 'run', '--rm', '--network', 'host', '--user', '0:0',
           '-v', '/workspace:/workspace', '-w', '/workspace/benchmarks', '--entrypoint', 'php', 'tracewick-signal-runtime:8.5', *args]
    return subprocess.check_output(cmd, text=True)


def fcgi(run):
    def record(kind, data=b''):
        return struct.pack('!BBHHBB', 1, kind, 1, len(data), 0, 0) + data
    params = {'SCRIPT_FILENAME': SCRIPTS + '/fpm.php', 'QUERY_STRING': 'run=' + run,
              'REQUEST_METHOD': 'GET', 'SERVER_PROTOCOL': 'HTTP/1.1', 'SERVER_NAME': 'localhost',
              'SERVER_PORT': '9000', 'REQUEST_URI': '/signal', 'CONTENT_LENGTH': '0'}
    payload = b''.join(bytes([len(k), len(v)]) + k.encode() + v.encode() for k, v in params.items())
    with socket.create_connection(('127.0.0.1', 9000), timeout=10) as conn:
        conn.sendall(record(1, struct.pack('!HB5x', 1, 0)) + record(4, payload) + record(4) + record(5))
        output = b''
        def read(size):
            data = b''
            while len(data) < size:
                chunk = conn.recv(size - len(data))
                if not chunk:
                    raise EOFError('FastCGI closed early')
                data += chunk
            return data
        while True:
            _, kind, _, length, padding, _ = struct.unpack('!BBHHBB', read(8))
            data = read(length)
            read(padding)
            if kind == 6:
                output += data
            if kind == 3:
                assert struct.unpack('!I', data[:4])[0] == 0
                return json.loads(output.split(b'\r\n\r\n', 1)[1])


def query(method, body):
    request = urllib.request.Request('http://127.0.0.1:4040/querier.v1.QuerierService/' + method,
                                     json.dumps(body).encode(), {'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def main():
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 4051), Proxy)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    results = []
    for runtime in ('cli', 'fpm', 'rr'):
        run = RUN + runtime
        if runtime == 'cli':
            captures = [json.loads(line) for line in php(SCRIPTS + '/cli.php', run).splitlines()]
        elif runtime == 'fpm':
            captures = [fcgi(run) for _ in range(10)]
        else:
            captures = []
            for _ in range(10):
                with urllib.request.urlopen('http://127.0.0.1:8089/?run=' + run, timeout=10) as response:
                    captures.append(json.load(response))
            assert len({c['pid'] for c in captures}) == 1, 'RR must reuse one worker'
        directory = ROOT / f'{runtime}-{run}'
        subprocess.run(['docker', 'run', '--rm', '-v', '/workspace:/workspace', 'busybox:1.36', 'chmod', '-R', 'a+rwX', str(directory)], check=True)
        spools = [json.loads(line) for line in php(SCRIPTS + '/inspect-spool.php', str(directory)).splitlines()]
        assert len(spools) == len(captures) == 10
        expected = sum(c['native_events'] for c in captures)
        assert sum(c['profile_events'] for c in captures) == expected
        assert sum(s['events'] for s in spools) == expected
        php_values = sum((values(path.read_bytes()) for path in directory.rglob('*.php.pprof')), [])
        assert sum(php_values) == expected * 1_000_000
        start = len(PUSHES)
        subprocess.run(['docker', 'run', '--rm', '--network', 'host', '-v', '/workspace:/workspace', '--entrypoint', '/workspace/signal-verification/tracewick-agent', 'tracewick-signal-runtime:8.5', 'run', '--once', '--spool-dir=' + str(directory),
                        '--pyroscope-url=http://127.0.0.1:4051', '--reader-id=signal-check'], check=True, capture_output=True, timeout=120)
        pushed = PUSHES[start:]
        assert pushed, 'No delivered profiles'
        go_values = sum((p['values'] for p in pushed), [])
        assert sum(go_values) == expected * 1_000_000
        assert not list(directory.rglob('*.spool')), 'Agent did not ack spool'
        assert not any('.claimed-' in p.name for p in directory.rglob('*')), 'Unacknowledged claim remains'
        app = spools[0]['application']
        deadline = time.monotonic() + 90
        backend = None
        while time.monotonic() < deadline:
            types = query('ProfileTypes', {'start': int(time.time() * 1000) - 600000, 'end': int(time.time() * 1000) + 60000})
            ids = [t['ID'] if 'ID' in t else t['id'] for t in types.get('profileTypes', []) if t.get('name') == 'wall']
            if ids:
                now = int(time.time() * 1000)
                backend = query('SelectMergeStacktraces', {'profileTypeID': ids[0], 'labelSelector': '{service_name="' + app + '"}',
                                                           'start': now - 600000, 'end': now + 60000})
                (directory / 'querier.json').write_text(json.dumps(backend, indent=2))
                graph = backend.get('flamegraph', {})
                total = graph.get('total')
                if total is not None and int(total) == expected * 1_000_000 and 'signalWork' in graph.get('names', []):
                    break
            time.sleep(1)
        else:
            raise AssertionError(f'Pyroscope total mismatch, expected {expected * 1000000}, got {backend}')
        results.append({'runtime': runtime, 'requests': 10, 'pids': sorted({c['pid'] for c in captures}),
                        'native_events': expected, 'spool_events': sum(s['events'] for s in spools),
                        'php_pprof_ns': sum(php_values), 'agent_pprof_ns': sum(go_values), 'pyroscope_ns': int(total),
                        'push_count': len(pushed), 'directory': str(directory)})
        print(json.dumps(results[-1]), flush=True)
        (ROOT / ('summary-' + RUN + '.json')).write_text(json.dumps(results, indent=2))
    server.shutdown()


if __name__ == '__main__':
    main()
