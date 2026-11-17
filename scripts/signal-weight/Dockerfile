FROM ghcr.io/roadrunner-server/roadrunner:2025.1.15 AS rr
FROM composer:2 AS composer
FROM php:8.5-fpm-bookworm
ARG EXCIMER_REF=23f541b9d970db0524a1b2506b4df727e5e59998
RUN --mount=type=secret,id=proxy_ca \
    apt-get update && apt-get install -y --no-install-recommends $PHPIZE_DEPS git unzip && \
    if [ -f /run/secrets/proxy_ca ]; then export GIT_SSL_CAINFO=/run/secrets/proxy_ca; fi && \
    git clone https://github.com/wikimedia/php-excimer.git /tmp/excimer && \
    cd /tmp/excimer && git checkout "$EXCIMER_REF" && phpize && ./configure && make -j2 && make install && \
    docker-php-ext-enable excimer && rm -rf /tmp/excimer /var/lib/apt/lists/*
COPY --from=rr /usr/bin/rr /usr/local/bin/rr
COPY --from=composer /usr/bin/composer /usr/local/bin/composer
WORKDIR /workspace/benchmarks
