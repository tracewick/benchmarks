# Tracewick benchmarks — capacity stand helpers.
#
#   make build           build workload images
#   make up              observability + app + drain
#   make down            stop and remove volumes
#   make bench-smoke     short k6 smoke against :8080
#   make collect-report  stash host meta under reports/_local/

SHELL := /bin/bash
.DEFAULT_GOAL := help

COMPOSE ?= docker compose
K6_IMAGE ?= grafana/k6:1.8.2
REPORTS_DIR ?= reports/_local
BASE_URL ?= http://127.0.0.1:8080
APP_PORT ?= 8080
GRAFANA_PORT ?= 3000
PYROSCOPE_PORT ?= 4040

.PHONY: help build up down up-chaos wait-ready wait-app k6-version bench-smoke collect-report smoke-check

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
	@mkdir -p "$(CURDIR)/$(REPORTS_DIR)"
	docker run --rm --network host \
		-v "$(CURDIR)/generators/k6:/scripts:ro" \
		-v "$(CURDIR)/$(REPORTS_DIR):/out" \
		-e BASE_URL="$(BASE_URL)" \
		-e VUS="$${VUS:-5}" \
		-e DURATION="$${DURATION:-45s}" \
		$(K6_IMAGE) run /scripts/smoke.js --summary-export=/out/smoke-summary.json
	@$(MAKE) --no-print-directory smoke-check

smoke-check: ## Confirm profiles landed in Pyroscope for benchmarks-workload
	@mkdir -p "$(CURDIR)/$(REPORTS_DIR)"
	PYROSCOPE_URL="http://127.0.0.1:$(PYROSCOPE_PORT)" \
		OUT="$(CURDIR)/$(REPORTS_DIR)/pyroscope-routes.json" \
		TIMEOUT=60 \
		"$(CURDIR)/scripts/check-profiles.sh"

collect-report: ## Gather local host meta under reports/_local/
	@mkdir -p "$(CURDIR)/$(REPORTS_DIR)"
	@uname -a > "$(CURDIR)/$(REPORTS_DIR)/uname.txt"
	@date -u +"collected_at=%Y-%m-%dT%H:%M:%SZ" > "$(CURDIR)/$(REPORTS_DIR)/meta.txt"
	@echo "K6_IMAGE=$(K6_IMAGE)" >> "$(CURDIR)/$(REPORTS_DIR)/meta.txt"
	@echo "BASE_URL=$(BASE_URL)" >> "$(CURDIR)/$(REPORTS_DIR)/meta.txt"
	@git rev-parse HEAD >> "$(CURDIR)/$(REPORTS_DIR)/meta.txt" 2>/dev/null || true
	@echo "Wrote $(REPORTS_DIR)/uname.txt and meta.txt"
