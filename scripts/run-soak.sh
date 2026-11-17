#!/usr/bin/env bash
# Observed soak: explicit pins, baseline/warmup/steady/drain/cooldown and validity gates.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"
exec python3 scripts/soak.py
