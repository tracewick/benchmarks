#!/usr/bin/env bash
# Disposable correctness stand. Fixed /workspace sibling layout; ports 4040/4051/8089/9000.
set -euo pipefail
cd /workspace/benchmarks
mkdir -p /workspace/signal-verification/output
chmod 777 /workspace/signal-verification/output
cp scripts/signal-weight/composer.{json,lock} /workspace/signal-verification/
# For networks with a proxy CA, set SIGNAL_PROXY_CA to its local PEM path.
build_args=()
if [[ -n "${SIGNAL_PROXY_CA:-}" ]]; then build_args+=(--secret "id=proxy_ca,src=$SIGNAL_PROXY_CA"); fi
docker build "${build_args[@]}" -t tracewick-signal-runtime:8.5 -f scripts/signal-weight/Dockerfile /workspace/signal-verification
composer_args=()
if [[ -n "${SIGNAL_PROXY_CA:-}" ]]; then
  composer_args+=(-v "$SIGNAL_PROXY_CA:/run/host-ca.pem:ro" -e COMPOSER_CAFILE=/run/host-ca.pem)
fi
docker run --rm --network host "${composer_args[@]}" -v /workspace:/workspace --entrypoint composer tracewick-signal-runtime:8.5 \
  install --working-dir=/workspace/signal-verification --no-interaction --no-progress --ignore-platform-reqs
(cd /workspace/agent && go build -o /workspace/signal-verification/tracewick-agent ./cmd/tracewick-agent)
docker run -d --name signal-pyroscope -p 127.0.0.1:4040:4040 -e HTTP_PROXY= -e HTTPS_PROXY= -e ALL_PROXY= -e NO_PROXY='*' \
  grafana/pyroscope:2.4.2 -server.http-listen-port=4040 -metastore.min-ready-duration=0 -ingester.min-ready-duration=0 -segment-writer.min-ready-duration=0
docker run -d --name signal-fpm --network host -v /workspace:/workspace -w /workspace/benchmarks tracewick-signal-runtime:8.5 sh -c \
  "sed -i 's/user = www-data/user = root/;s/group = www-data/group = root/;s/^listen = 9000/listen = 127.0.0.1:9000/' /usr/local/etc/php-fpm.d/www.conf; exec php-fpm -R"
docker run -d --name signal-rr --network host -v /workspace:/workspace -w /workspace/benchmarks --entrypoint rr \
  tracewick-signal-runtime:8.5 serve -c scripts/signal-weight/rr.yaml
for ((attempt=0; attempt<90; attempt++)); do
  if curl -fsS http://127.0.0.1:4040/ready >/dev/null; then
    python3 scripts/signal-weight/verify.py
    exit 0
  fi
  sleep 1
done
exit 1
