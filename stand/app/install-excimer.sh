#!/bin/sh
# Optional exact source pin for benchmark builds; otherwise retain the PECL stand path.
set -eu
if [ -f /run/secrets/proxy_ca ]; then export GIT_SSL_CAINFO=/run/secrets/proxy_ca; fi
if [ -n "${EXCIMER_REF:-}" ]; then
    test "${#EXCIMER_REF}" -eq 40
    git init /tmp/excimer
    git -C /tmp/excimer remote add origin https://github.com/wikimedia/php-excimer.git
    git -C /tmp/excimer fetch --depth=1 origin "$EXCIMER_REF"
    git -C /tmp/excimer checkout --detach FETCH_HEAD
    test "$(git -C /tmp/excimer rev-parse HEAD)" = "$EXCIMER_REF"
    cd /tmp/excimer
    phpize
    ./configure
    make -j2
    make install
    rm -rf /tmp/excimer
else
    pecl install "excimer-${EXCIMER_VERSION}"
fi
docker-php-ext-enable excimer
php -r 'exit(phpversion("excimer") === getenv("EXCIMER_VERSION") ? 0 : 1);'
