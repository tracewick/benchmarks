#!/usr/bin/env bash
set -euo pipefail

probe_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source_dir=$(mktemp -d)
trap 'rm -rf -- "$source_dir"' EXIT
git clone --quiet --depth 1 --branch 1.2.7 \
  https://github.com/wikimedia/mediawiki-php-excimer.git "$source_dir/excimer"
git clone --quiet --depth 1 --branch v1.2.15 \
  https://github.com/krakjoe/parallel.git "$source_dir/parallel"
test "$(git -C "$source_dir/excimer" rev-parse HEAD)" = 23f541b9d970db0524a1b2506b4df727e5e59998
test "$(git -C "$source_dir/parallel" rev-parse HEAD)" = f62fab1225f687de60d789002c9b49467d3e04de
docker build --build-context "excimer=$source_dir/excimer" \
  --build-context "parallel=$source_dir/parallel" \
  -f "$probe_dir/Dockerfile" -t tracewick-zts-parallel:8.5 "$probe_dir"
