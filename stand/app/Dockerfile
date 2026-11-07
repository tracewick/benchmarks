# syntax=docker/dockerfile:1
#
# Minimal PHP-FPM + RoadRunner workload for Tracewick benchmarks (Packagist pin).

ARG PHP_VERSION=8.4
ARG EXCIMER_VERSION=1.2.6
ARG TRACEWICK_VERSION=0.1.0
ARG NGINX_VERSION=1.28.0
ARG ROADRUNNER_VERSION=2025.1.15

FROM composer:2 AS vendor

ARG TRACEWICK_VERSION=0.1.0

WORKDIR /app
COPY composer.json ./
# Pin is in composer.json; TRACEWICK_VERSION must match that constraint when rebuilding.
RUN test -n "${TRACEWICK_VERSION}" \
    && composer update --no-interaction --no-progress --no-dev \
    && composer clear-cache \
    && composer show tracewick/tracewick | head -5

FROM ghcr.io/roadrunner-server/roadrunner:${ROADRUNNER_VERSION} AS roadrunner-binary

FROM php:${PHP_VERSION}-cli-bookworm AS php-base

ARG EXCIMER_VERSION=1.2.6

RUN apt-get update \
    && apt-get install -y --no-install-recommends git unzip \
    && rm -rf /var/lib/apt/lists/* \
    && docker-php-ext-install -j"$(nproc)" pcntl sockets \
    && pecl install "excimer-${EXCIMER_VERSION}" \
    && docker-php-ext-enable excimer \
    && rm -rf /tmp/pear \
    && php -r 'exit(extension_loaded("excimer") ? 0 : 1);' \
    && install -d -o www-data -g www-data /var/spool/tracewick

WORKDIR /srv/app
COPY --from=vendor /app/vendor /srv/app/vendor
COPY --from=vendor /app/composer.json /app/composer.lock /srv/app/
COPY public /srv/app/public
COPY src /srv/app/src
COPY worker.php /srv/app/worker.php
COPY .rr.yaml /srv/app/.rr.yaml

ENV TRACEWICK_SPOOL_DIR=/var/spool/tracewick \
    TRACEWICK_SAMPLE_RATE=1.0 \
    TRACEWICK_SERVICE=benchmarks-workload \
    TRACEWICK_ENV=bench

FROM php:${PHP_VERSION}-fpm-bookworm AS fpm

ARG EXCIMER_VERSION=1.2.6

RUN apt-get update \
    && apt-get install -y --no-install-recommends git unzip \
    && rm -rf /var/lib/apt/lists/* \
    && docker-php-ext-install -j"$(nproc)" pcntl \
    && pecl install "excimer-${EXCIMER_VERSION}" \
    && docker-php-ext-enable excimer \
    && rm -rf /tmp/pear \
    && php -r 'exit(extension_loaded("excimer") ? 0 : 1);' \
    && install -d -o www-data -g www-data /var/spool/tracewick

WORKDIR /srv/app
COPY --from=vendor /app/vendor /srv/app/vendor
COPY --from=vendor /app/composer.json /app/composer.lock /srv/app/
COPY public /srv/app/public
COPY src /srv/app/src
COPY php-fpm.conf /usr/local/etc/php-fpm.d/zz-benchmarks.conf
COPY docker-fpm-entrypoint.sh /usr/local/bin/docker-fpm-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-fpm-entrypoint.sh

ENV TRACEWICK_SPOOL_DIR=/var/spool/tracewick \
    TRACEWICK_SAMPLE_RATE=1.0 \
    TRACEWICK_SERVICE=benchmarks-workload \
    TRACEWICK_ENV=bench \
    PHP_FPM_MAX_CHILDREN=4

# Master runs as root (pool workers are www-data); entrypoint rewrites pm.max_children.
ENTRYPOINT ["/usr/local/bin/docker-fpm-entrypoint.sh"]
CMD ["php-fpm"]

FROM php-base AS roadrunner
COPY --from=roadrunner-binary /usr/bin/rr /usr/local/bin/rr
COPY docker-rr-entrypoint.sh /usr/local/bin/docker-rr-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-rr-entrypoint.sh
ENV RR_NUM_WORKERS=4
USER www-data
ENTRYPOINT ["/usr/local/bin/docker-rr-entrypoint.sh"]
CMD []

FROM nginx:${NGINX_VERSION}-alpine AS nginx
COPY nginx.conf /etc/nginx/conf.d/default.conf
