"""Deterministic /proc teardown races in the shell collector."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from soaklib import parse_processes

PROBE = (Path(__file__).resolve().parents[1] / 'scripts/soak_probe.sh').read_text()


class ProbeTest(unittest.TestCase):
    def run_probe(self, failure, disappear=False):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proc = root / 'proc'
            for pid in (10, 20):
                process = proc / str(pid)
                process.mkdir(parents=True)
                (process / 'comm').write_text('php\n')
                (process / 'cmdline').write_bytes(b'php\0worker.php\0')
                fields = ['S'] + ['0'] * 19
                fields[19] = str(pid * 100)
                (process / 'stat').write_text(f'{pid} (php) ' + ' '.join(fields) + '\n')
                (process / 'status').write_text('VmRSS:\t8 kB\nRssAnon:\t4 kB\nThreads:\t2\n')
                (process / 'fd').mkdir()
                (process / 'fd/0').symlink_to('/dev/null')
            binaries = root / 'bin'
            binaries.mkdir()
            # Process 20 exits after its cmdline was read. Process 10 is stable.
            cat = binaries / 'cat'
            cat.write_text('''#!/bin/sh
if [ "$1" = "$PROBE_FIXTURE/20/stat" ]; then
    if [ "$PROBE_DISAPPEAR" = 1 ]; then rm -r "$PROBE_FIXTURE/20"; fi
    exit 1
fi
exec /bin/cat "$@"
''')
            cat.chmod(0o755)
            find = binaries / 'find'
            find.write_text('''#!/bin/sh
if [ "$1" = "$PROBE_FIXTURE/10/fd" ]; then exit 1; fi
exec /usr/bin/find "$@"
''')
            find.chmod(0o755)
            if failure == 'stat':
                find.unlink()
            else:
                cat.unlink()
            env = {**os.environ, 'PATH': str(binaries) + ':' + os.environ['PATH'],
                   'PROBE_FIXTURE': str(proc), 'PROBE_DISAPPEAR': '1' if disappear else '0'}
            script = PROBE.replace('/proc/', str(proc) + '/')
            return subprocess.run(['sh'], input=script, text=True, capture_output=True, env=env)

    def test_exited_process_cannot_leave_a_partial_record(self):
        result = self.run_probe('stat', disappear=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual([10], [p['pid'] for p in parse_processes(result.stdout)])
        self.assertNotIn('@ 20', result.stdout)

    def test_live_process_read_failure_is_reported(self):
        result = self.run_probe('stat')
        self.assertNotEqual(0, result.returncode)
        self.assertIn('Cannot read stat for PID 20 (php)', result.stderr)

    def test_failed_descriptor_read_cannot_become_zero(self):
        result = self.run_probe('fd')
        self.assertNotEqual(0, result.returncode)
        self.assertIn('Cannot read fd for PID 10 (php)', result.stderr)
        self.assertEqual('', result.stdout)


if __name__ == '__main__':
    unittest.main()
