# Adapter HTTP overhead

Follow [METHOD.md](../../METHOD.md). The benchmark compares profiling off and on
within each adapter and runtime. All arms use one worker and the same deterministic
PHP work and check every HTTP response with k6. The Symfony and Laravel fixtures
reuse their real HTTP kernels behind a minimal RoadRunner bridge.

## Inputs

- PSR-15 at `bb4dd1629231cdf167247399c72c751d40e06dfd`, with Composer dependencies
  installed in each runtime example. Install against this source checkout so the
  local Composer path repository resolves the measured middleware. See the
  [dependency pins](../../reports/2026-11-27-adapter-http-overhead/psr-dependencies.json).
- Symfony bundle at `1bb2f2678bed6cba75a2635b95faa2fdb7a04db4` and Laravel adapter
  at `bb93ad08efcfb732b95745b3d491aa2f622987c2`. The two fixture locks install
  the frameworks and common core RC. The adapter code comes from the pinned
  checkout archives, so installed dev tools and test polyfills stay outside the fixtures.
- The PSR-15 example Dockerfiles build the Swoole and FrankenPHP images.
  RoadRunner needs PHP CLI 8.5.12 NTS with Excimer 1.2.7 and sockets. The run used
  `tracewick-cloud-php:8.5` and mounted RoadRunner 2025.1.15 under `/rr` along
  with its ABI-matching sockets module. Set `ADAPTER_RR_DIR` to a directory with
  `rr`, `sockets.so` and `sockets.ini` containing `extension=/rr/sockets.so`.
- Set `ADAPTER_WORKSPACE` to the parent of the `psr-15` checkout and
  `ADAPTER_FRAMEWORK_INPUTS` to the directory of pinned adapter archives.
  Image overrides are `ADAPTER_RR_IMAGE`, `ADAPTER_SWOOLE_IMAGE`,
  `ADAPTER_FRANKEN_IMAGE` and `ADAPTER_K6_IMAGE`. Docker host networking and
  loopback port 18150 must be available.

From this directory, install the two fixtures using Composer under PHP 8.5:

```sh
composer --working-dir=symfony install --no-dev --prefer-dist
composer --working-dir=laravel install --no-dev --prefer-dist
```

Prepare inputs from the checked-out repositories:

```sh
export ADAPTER_WORKSPACE=/path/to/checkouts
export ADAPTER_FRAMEWORK_INPUTS="$(mktemp -d)"
mkdir -p "$ADAPTER_FRAMEWORK_INPUTS/symfony" "$ADAPTER_FRAMEWORK_INPUTS/laravel"
git -C "$ADAPTER_WORKSPACE/symfony-bundle" archive 1bb2f2678bed6cba75a2635b95faa2fdb7a04db4 src |
    tar -x -C "$ADAPTER_FRAMEWORK_INPUTS/symfony"
git -C "$ADAPTER_WORKSPACE/laravel" archive bb93ad08efcfb732b95745b3d491aa2f622987c2 src config |
    tar -x -C "$ADAPTER_FRAMEWORK_INPUTS/laravel"
```

## Run

```sh
results="$(mktemp -d)"
./run.sh "$results" 60s 20s \
    rr:0:1 rr:1:1 rr:1:2 rr:0:2 \
    franken:0:1 franken:1:1 franken:1:2 franken:0:2 \
    swoole:0:1 swoole:1:1 swoole:1:2 swoole:0:2 \
    symfony:0:1 symfony:1:1 symfony:1:2 symfony:0:2 \
    laravel:0:1 laravel:1:1 laravel:1:2 laravel:0:2
python3 summarize.py "$results" --json "$results/measurements.json"
```

The report figure was rendered with Matplotlib 3.10.8:

```sh
python3 plot.py "$results/measurements.json" "$results/paired-deltas.png"
```

Each fresh container gets 128 MiB of shared memory for the spool and its
64 MiB free-space reserve. Arms are sequential. The result includes warmup and
measurement k6 metrics, start and end process counters, and the spool inventory.
A checksum mismatch, wrong worker PID, failed request, dropped iteration, or
unexpected spool presence fails the run.
