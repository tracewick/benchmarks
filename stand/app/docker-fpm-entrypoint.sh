#!/bin/sh
# Apply PHP_FPM_MAX_CHILDREN then start php-fpm (official entrypoint).
set -eu
MAX=${PHP_FPM_MAX_CHILDREN:-4}
case "$MAX" in
  ''|*[!0-9]*)
    echo "PHP_FPM_MAX_CHILDREN must be a positive integer, got: $MAX" >&2
    exit 1
    ;;
esac
if [ "$MAX" -lt 1 ]; then
  echo "PHP_FPM_MAX_CHILDREN must be >= 1" >&2
  exit 1
fi
sed -i "s/^pm.max_children = .*/pm.max_children = ${MAX}/" \
  /usr/local/etc/php-fpm.d/zz-benchmarks.conf
exec docker-php-entrypoint "$@"
