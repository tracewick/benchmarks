#!/usr/bin/env python3
"""Derive the fixed-iteration worker from the repository's normal RR fixture."""
import argparse
import shutil
from pathlib import Path

root = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser()
parser.add_argument('output', type=Path)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
source = (root / 'stand/app/worker.php').read_text()
old = '''            if ($effectiveDepth > 0) {
                deepStackWork($effectiveDepth, $effectiveBusy);
            } else {
                busyWork($effectiveBusy);
            }'''
assert source.count(old) == 1, 'RR fixture changed; review the fixed-work adapter'
source = source.replace(old, "            $checksum = fixedStackWork($effectiveDepth, $route === 'ping' ? 0 : $iterations);")
source = source.replace("require __DIR__ . '/src/SyntheticWork.php';", "require __DIR__ . '/fixed-work.php';")
source = source.replace("$busyMs = max(0, (int) (getenv('WORK_BUSY_MS') ?: '25'));",
                        "$iterations = max(1, (int) getenv('WORK_ITERATIONS'));\n$expectedChecksum = (int) getenv('WORK_CHECKSUM');")
source = source.replace("            $effectiveBusy = $route === 'ping' ? 0 : $busyMs;\n", '')
source = source.replace("'busy_ms' => $effectiveBusy,", "'busy_ms' => null,\n                'work_mode' => 'fixed-iterations',\n                'work_iterations' => $route === 'ping' ? 0 : $iterations,\n                'work_checksum' => $checksum,")
source = source.replace("'work_stack_depth' => $stackDepth,", "'work_stack_depth' => $stackDepth,\n                'work_mode' => 'fixed-iterations',\n                'work_iterations' => $iterations,\n                'work_expected_checksum' => $expectedChecksum,")
(args.output / 'worker.php').write_text(source)
shutil.copyfile(Path(__file__).with_name('fixed-work.php'), args.output / 'fixed-work.php')
(args.output / 'Dockerfile').write_text(
    'FROM tracewick-benchmarks-rr:runtime-preflight\n'
    'COPY worker.php /srv/app/worker.php\n'
    'COPY fixed-work.php /srv/app/fixed-work.php\n')
