#!/usr/bin/env python3
"""Paired overhead control with the same work count and checksum in every arm."""
import hashlib
import json
import os
import time
from pathlib import Path

from overhead import Overhead
from soaklib import command

class FixedOverhead(Overhead):
    def __init__(self, iterations, checksum):
        super().__init__()
        self.iterations = iterations
        self.checksum = checksum
        script = self.harness / 'soak.js'
        original = script.read_text()
        needle = 'r.json("ok") === true'
        assert original.count(needle) == 1
        replacement = (needle + ' && r.json("work_mode") === "fixed-iterations"'
                       + ' && r.json("work_iterations") === ' + str(iterations)
                       + ' && r.json("work_checksum") === ' + str(checksum))
        script.write_text(original.replace(needle, replacement))
        self.identity['fixed_work'] = {'iterations': iterations, 'checksum': checksum,
            'k6_script_sha256': hashlib.sha256(script.read_bytes()).hexdigest()}

    def health(self, enabled):
        result = super().health(enabled)
        if (result.get('work_mode') != 'fixed-iterations'
                or result.get('work_iterations') != self.iterations
                or result.get('work_expected_checksum') != self.checksum):
            raise ValueError('Fixed workload configuration differs from calibration')
        return result

def main():
    parent = Path(os.environ['REPORTS_DIR']).resolve()
    parent.mkdir(parents=True, exist_ok=True)
    iterations = int(os.environ['WORK_ITERATIONS'])
    checksum = int(os.environ['WORK_CHECKSUM'])
    assert iterations > 0
    project = os.environ['SOAK_PROJECT']
    assert not command(['docker','compose','-p',project,'--profile','agent','ps','-aq'])
    index = []
    for number, enabled in enumerate((False, True, True, False, False, True), 1):
        observer = FixedOverhead(iterations, checksum)
        entry = {'number': number, 'enabled': enabled, 'directory': str(observer.directory),
                 'started_at': time.time(), 'status': 'running'}
        index.append(entry)
        try:
            if number == 1:
                observer.compose_run('up','-d','--no-deps','pyroscope')
                observer.wait_ready(observer.pyroscope_url + '/ready')
            print(f'FIXED PHASE {number}/6 enabled={enabled}', flush=True)
            result = observer.measure(enabled, '1m', '5m')
            entry['status'] = result['status']
            entry['ended_at'] = time.time()
        except Exception as error:
            entry['status'] = 'failed'
            entry['error'] = str(error)
            raise
        finally:
            (parent/'fixed-index.json').write_text(json.dumps(index,indent=2)+'\n')
    print('FIXED-WORK CAMPAIGN PASSED',flush=True)


if __name__ == '__main__':
    main()
