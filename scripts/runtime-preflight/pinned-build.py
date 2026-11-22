#!/usr/bin/env python3
"""Reuse the soak's exact platform images while testing new product source SHAs."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser()
parser.add_argument('output_directory', type=Path)
args = parser.parse_args()
out = args.output_directory.resolve()
out.mkdir(parents=True, exist_ok=True)
pins = {
    'php_cli': 'php:8.4-cli-bookworm@sha256:b3e907a1108629c562c4bb313ce3449e34d49991f6bb2487913f6146f47200fe',
    'composer': 'composer:2@sha256:0c8e663f14c94d07b3c45b175c51f5a14718508f21fe4dd7e54f09488dd0ed71',
    'golang': 'golang:1.27.4-bookworm@sha256:4fa7c968ba93f1635670522dbb01a2c78150443e1385746924566079f36570ea',
    'debian': 'debian:bookworm-slim@sha256:734a72b3d6142a71993b4bc580ca01d8ca687f77a2c422d96a961d3376b179bc',
}
app = (ROOT / 'stand/app/Dockerfile').read_text()
app = app.replace('FROM composer:2 AS vendor', 'FROM ' + pins['composer'] + ' AS vendor')
app = app.replace('FROM php:${PHP_VERSION}-cli-bookworm AS php-base', 'FROM ' + pins['php_cli'] + ' AS php-base')
agent = (ROOT / 'stand/agent/Dockerfile').read_text()
agent = agent.replace('FROM golang:1.27.4-bookworm AS source-build', 'FROM ' + pins['golang'] + ' AS source-build')
agent = agent.replace('FROM debian:bookworm-slim AS ', 'FROM ' + pins['debian'] + ' AS ')
(out / 'app.Dockerfile').write_text(app)
(out / 'agent.Dockerfile').write_text(agent)
(out / 'platform-pins.json').write_text(json.dumps(pins, indent=2) + '\n')
(out / 'compose-build.json').write_text(json.dumps({'services': {
    'app-rr': {'build': {'dockerfile': str(out / 'app.Dockerfile')}},
    'app-agent': {'build': {'dockerfile': str(out / 'agent.Dockerfile')}},
}}, indent=2) + '\n')
