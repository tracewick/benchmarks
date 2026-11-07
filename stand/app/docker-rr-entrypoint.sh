#!/bin/sh
set -eu
workers=${RR_NUM_WORKERS:-4}
# RoadRunner yaml has no env interpolation for num_workers — stamp it in.
sed "s/num_workers: .*/num_workers: ${workers}/" /srv/app/.rr.yaml > /tmp/rr.yaml
exec rr serve -c /tmp/rr.yaml
