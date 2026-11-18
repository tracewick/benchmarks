#!/usr/bin/env python3
"""Check targeted strace calls between explicit callback markers."""
import argparse
import json
import re
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('trace', type=Path)
args = parser.parse_args()
depth = 0
markers = 0
calls = []
marker_pattern = re.compile(r'^\s*(?:\d+\s+)?write\(\d+,\s*"OTEL_CB_(BEGIN|END)\\n"')
for line in args.trace.read_text().splitlines():
    marker = marker_pattern.match(line)
    if marker and marker.group(1) == 'BEGIN':
        depth += 1
        markers += 1
    elif marker and marker.group(1) == 'END':
        depth -= 1
        if depth < 0:
            raise SystemExit('Unbalanced callback markers')
    elif depth:
        calls.append(line)
result = {'marked_callbacks': markers, 'targeted_syscalls': len(calls),
          'balanced_markers': depth == 0, 'examples': calls[:5]}
result['pass'] = markers > 0 and depth == 0 and not calls
print(json.dumps(result, indent=2))
raise SystemExit(0 if result['pass'] else 1)
