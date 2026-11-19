ARG PHP_IMAGE=php:8.5.12-zts-bookworm@sha256:c6a2606c831a21992c2cdd0ae5a4e87af02348c4c3f66621bfb8b87702977ee3
FROM ${PHP_IMAGE}

# Supply the pinned public extension checkouts as named build contexts.
COPY --from=excimer / /tmp/excimer/
COPY --from=parallel / /tmp/parallel/
RUN cd /tmp/excimer \
    && phpize && ./configure --enable-excimer && make -j2 && make install \
    && cd /tmp/parallel \
    && phpize && ./configure --enable-parallel && make -j2 && make install \
    && docker-php-ext-enable excimer parallel \
    && rm -rf /tmp/excimer /tmp/parallel

CMD ["php", "--version"]
