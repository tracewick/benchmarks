ARG PHP_BASE=tracewick-benchmarks-rr:runtime-preflight
FROM composer:2@sha256:0c8e663f14c94d07b3c45b175c51f5a14718508f21fe4dd7e54f09488dd0ed71 AS composer
FROM ${PHP_BASE}
USER root
COPY --from=composer /usr/bin/composer /usr/local/bin/composer
RUN apt-get update \
    && apt-get install -y --no-install-recommends libxml2-dev libonig-dev \
    && docker-php-ext-install -j2 dom mbstring xml xmlwriter \
    && rm -rf /var/lib/apt/lists/*
COPY bundle /sources/bundle
WORKDIR /srv/bundle
ARG TRACEWICK_VERSION
ENV COMPOSER_ALLOW_SUPERUSER=1 COMPOSER_ROOT_VERSION=dev-develop
# Keep the original snapshot for a separate package-metadata installation probe.
# Pin core explicitly in the root test project to exercise bundle runtime code.
RUN cp -a /sources/bundle/. /srv/bundle/ \
    && php -r '$p=json_decode(file_get_contents("composer.json"),true,512,JSON_THROW_ON_ERROR);$p["require"]["tracewick/tracewick"]=getenv("TRACEWICK_VERSION");foreach(["symfony/framework-bundle","symfony/http-foundation","symfony/messenger","symfony/routing"] as $name){$p["require"][$name]="7.4.*";unset($p["require-dev"][$name]);}foreach(["require","require-dev"] as $group){foreach($p[$group] as $name=>$version){if(str_starts_with($name,"symfony/")){$p[$group][$name]="7.4.*";}}}file_put_contents("composer.json",json_encode($p,JSON_PRETTY_PRINT|JSON_UNESCAPED_SLASHES|JSON_THROW_ON_ERROR));' \
    && composer update --no-interaction --no-progress --prefer-dist --no-scripts
USER 33:33
ENTRYPOINT ["php"]
# Production consumers do not load the bundle's autoload-dev test polyfills.
USER root
RUN composer dump-autoload --no-dev --no-scripts
USER 33:33
