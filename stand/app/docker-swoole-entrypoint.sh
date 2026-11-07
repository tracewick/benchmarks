#!/bin/sh
set -eu
# SWOOLE_WORKER_NUM is read by swoole-server.php; no yaml stamp needed.
exec php /srv/app/swoole-server.php
