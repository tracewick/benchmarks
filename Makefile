# Tracewick benchmarks — capacity stand helpers.
#
#   make up                 observability + app + drain
#   make bench-smoke        short wiring smoke
#   make bench-overhead     M2 baseline vs on @ fixed RPS + report

SHELL := /bin/bash
.DEFAULT_GOAL := help

COMPOSE ?= docker compose
K6_IMAGE ?= grafana/k6:1.8.2
REPORTS_DIR ?= reports/_local
BASE_URL ?= http://127.0.0.1:8080
APP_PORT ?= 8080
GRAFANA_PORT ?= 3000
PYROSCOPE_PORT ?= 4040
RATE ?= 20
DURATION ?= 2m

.PHONY: help build up down up-chaos wait-ready wait-app k6-version bench-smoke bench-overhead bench-spool-pressure bench-chaos bench-soak bench-rps prepare-reports-dir collect-report smoke-check

help: ## Show targets
	@awk 'BEGIN {FS = ":.*##"; printf "Targets:\n"} /^[a-zA-Z0-9_-]+:.*?##/ { printf "  %-18s %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

build: ## Build PHP-FPM (+ nginx) workload images
	$(COMPOSE) build app-fpm app-nginx

up: build ## Start Pyroscope, Grafana, app, drain
	$(COMPOSE) up -d --wait pyroscope grafana app-fpm app-nginx
	@$(MAKE) --no-print-directory wait-ready
	# Start drain after Pyroscope /ready so the first claim is not held across metastore warmup.
	$(COMPOSE) up -d app-drain
	@$(MAKE) --no-print-directory wait-app

up-chaos: build ## Start stack including Toxiproxy (profile chaos)
	$(COMPOSE) --profile chaos up -d --wait pyroscope grafana app-fpm app-nginx toxiproxy
	@$(MAKE) --no-print-directory wait-ready
	$(COMPOSE) up -d app-drain
	@$(MAKE) --no-print-directory wait-app

down: ## Stop the stand and remove volumes
	$(COMPOSE) --profile chaos down --volumes --remove-orphans

wait-ready: ## Poll Grafana health and Pyroscope /ready
	@echo "Waiting for Grafana…"
	@for i in $$(seq 1 60); do \
		curl -sf http://127.0.0.1:$(GRAFANA_PORT)/api/health >/dev/null && break; \
		sleep 1; \
	done
	@curl -sf http://127.0.0.1:$(GRAFANA_PORT)/api/health >/dev/null
	@echo "Waiting for Pyroscope /ready…"
	@for i in $$(seq 1 90); do \
		code=$$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:$(PYROSCOPE_PORT)/ready || true); \
		[ "$$code" = "200" ] && break; \
		sleep 1; \
	done
	@code=$$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:$(PYROSCOPE_PORT)/ready || true); \
		[ "$$code" = "200" ] || { echo "Pyroscope not ready (HTTP $$code)"; exit 1; }
	@echo "Observability ready."

wait-app: ## Poll workload /health
	@echo "Waiting for app $(BASE_URL)/health…"
	@for i in $$(seq 1 60); do \
		curl -sf "$(BASE_URL)/health" >/dev/null && break; \
		sleep 1; \
	done
	@curl -sf "$(BASE_URL)/health"
	@echo
	@echo "App ready."

k6-version: ## Show pinned k6 Docker image and its version string
	@echo "K6_IMAGE=$(K6_IMAGE)"
	docker run --rm $(K6_IMAGE) version

bench-smoke: ## Run the smoke k6 script (requires make up)
	@$(MAKE) --no-print-directory prepare-reports-dir
	# Ensure profiling on @ 1.0 so Pyroscope check is deterministic.
	TRACEWICK_ENABLED=1 TRACEWICK_SAMPLE_RATE=1.0 $(COMPOSE) up -d --force-recreate --no-deps app-fpm
	@$(MAKE) --no-print-directory wait-app
	docker run --rm --network host \
		-v "$(CURDIR)/generators/k6:/scripts:ro" \
		-v "$(CURDIR)/$(REPORTS_DIR):/out" \
		-e BASE_URL="$(BASE_URL)" \
		-e VUS="$${VUS:-5}" \
		-e DURATION="$${DURATION:-45s}" \
		$(K6_IMAGE) run /scripts/smoke.js --summary-export=/out/smoke-summary.json
	@$(MAKE) --no-print-directory smoke-check

bench-overhead: ## M2: baseline vs on @ fixed RPS; writes reports/_local/overhead-* 
	@chmod +x scripts/run-overhead.sh scripts/sample-container-stats.sh scripts/summarize-overhead.py
	RATE="$(RATE)" DURATION="$(DURATION)" BASE_URL="$(BASE_URL)" K6_IMAGE="$(K6_IMAGE)" \
		COMPOSE="$(COMPOSE)" REPORTS_DIR="$(REPORTS_DIR)" \
		./scripts/run-overhead.sh

bench-spool-pressure: ## M3: stop drain, fill spool to max_files, measure catch-up
	@chmod +x scripts/run-spool-pressure.sh scripts/spool-snapshot.sh
	RATE="$(RATE)" DURATION="$${DURATION:-90s}" BASE_URL="$(BASE_URL)" K6_IMAGE="$(K6_IMAGE)" \
		COMPOSE="$(COMPOSE)" REPORTS_DIR="$(REPORTS_DIR)" \
		TRACEWICK_SPOOL_MAX_FILES="$${TRACEWICK_SPOOL_MAX_FILES:-80}" \
		./scripts/run-spool-pressure.sh

bench-chaos: ## M3 optional: Toxiproxy latency toward Pyroscope
	@chmod +x scripts/run-chaos-pyroscope.sh scripts/spool-snapshot.sh
	RATE="$(RATE)" DURATION="$${DURATION:-60s}" BASE_URL="$(BASE_URL)" K6_IMAGE="$(K6_IMAGE)" \
		COMPOSE="$(COMPOSE)" REPORTS_DIR="$(REPORTS_DIR)" LATENCY_MS="$${LATENCY_MS:-3000}" \
		./scripts/run-chaos-pyroscope.sh

bench-soak: ## Soak: fixed RPS + FPM/drain RSS·CPU series (default RATE=10 DURATION=72h)
	@chmod +x scripts/run-soak.sh scripts/sample-container-stats.sh scripts/summarize-soak.py
	RATE="$${RATE:-10}" DURATION="$${DURATION:-72h}" BASE_URL="$(BASE_URL)" K6_IMAGE="$(K6_IMAGE)" \
		COMPOSE="$(COMPOSE)" REPORTS_DIR="$(REPORTS_DIR)" STATS_INTERVAL="$${STATS_INTERVAL:-60}" \
		TRACEWICK_SAMPLE_RATE="$${TRACEWICK_SAMPLE_RATE:-0.1}" \
		./scripts/run-soak.sh

bench-rps: ## High-RPS pipeline: deep stacks + spool series (default RATE=500 DURATION=5m)
	@chmod +x scripts/run-rps-pipeline.sh scripts/spool-snapshot.sh scripts/summarize-rps-pipeline.py
	RATE="$${RATE:-500}" DURATION="$${DURATION:-5m}" BASE_URL="$(BASE_URL)" K6_IMAGE="$(K6_IMAGE)" \
		COMPOSE="$(COMPOSE)" REPORTS_DIR="$(REPORTS_DIR)" STATS_INTERVAL="$${STATS_INTERVAL:-2}" \
		TRACEWICK_SAMPLE_RATE="$${TRACEWICK_SAMPLE_RATE:-0.1}" \
		WORK_STACK_DEPTH="$${WORK_STACK_DEPTH:-48}" \
		PHP_FPM_MAX_CHILDREN="$${PHP_FPM_MAX_CHILDREN:-32}" \
		WORK_BUSY_MS="$${WORK_BUSY_MS:-25}" WORK_SLEEP_MS="$${WORK_SLEEP_MS:-10}" \
		REQUEST_PATH="$${REQUEST_PATH:-/work}" DRAIN_MODE="$${DRAIN_MODE:-on}" \
		./scripts/run-rps-pipeline.sh

# k6 image runs as a non-root uid; world-writable _local avoids "permission denied" on /out.
prepare-reports-dir:
	@mkdir -p "$(CURDIR)/$(REPORTS_DIR)"
	@chmod a+rwx "$(CURDIR)/$(REPORTS_DIR)"

smoke-check: ## Confirm profiles landed in Pyroscope for benchmarks-workload
	@$(MAKE) --no-print-directory prepare-reports-dir
	PYROSCOPE_URL="http://127.0.0.1:$(PYROSCOPE_PORT)" \
		OUT="$(CURDIR)/$(REPORTS_DIR)/pyroscope-routes.json" \
		TIMEOUT=60 \
		"$(CURDIR)/scripts/check-profiles.sh"

collect-report: ## Gather local host meta under reports/_local/
	@$(MAKE) --no-print-directory prepare-reports-dir
	@uname -a > "$(CURDIR)/$(REPORTS_DIR)/uname.txt"
	@date -u +"collected_at=%Y-%m-%dT%H:%M:%SZ" > "$(CURDIR)/$(REPORTS_DIR)/meta.txt"
	@echo "K6_IMAGE=$(K6_IMAGE)" >> "$(CURDIR)/$(REPORTS_DIR)/meta.txt"
	@echo "BASE_URL=$(BASE_URL)" >> "$(CURDIR)/$(REPORTS_DIR)/meta.txt"
	@git rev-parse HEAD >> "$(CURDIR)/$(REPORTS_DIR)/meta.txt" 2>/dev/null || true
	@echo "Wrote $(REPORTS_DIR)/uname.txt and meta.txt"
