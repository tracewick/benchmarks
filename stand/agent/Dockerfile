# Thin image: public GitHub release binary (avoids private GHCR pulls).
# Runs as UID/GID 33 to match PHP-FPM www-data on the spool volume.
ARG AGENT_BUILD_TARGET=release

FROM golang:1.27.4-bookworm AS source-build
ARG AGENT_REF
WORKDIR /src
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export GIT_SSL_CAINFO=/run/secrets/proxy_ca SSL_CERT_FILE=/run/secrets/proxy_ca; fi; \
    test "${#AGENT_REF}" -eq 40 \
    && git init . \
    && git remote add origin https://github.com/tracewick/agent.git \
    && git fetch --depth=1 origin "${AGENT_REF}" \
    && git checkout --detach FETCH_HEAD \
    && test "$(git rev-parse HEAD)" = "${AGENT_REF}" \
    && CGO_ENABLED=0 go build -trimpath -ldflags "-s -w -X github.com/tracewick/agent/internal/version.Version=dev-${AGENT_REF}" -o /tracewick-agent ./cmd/tracewick-agent \
    && git rev-parse HEAD > /agent-reference

FROM debian:bookworm-slim AS release

ARG AGENT_VERSION=0.1.0
ARG TARGETARCH=amd64

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && curl -fsSL -o /tmp/agent.tgz \
      "https://github.com/tracewick/agent/releases/download/v${AGENT_VERSION}/tracewick-agent_${AGENT_VERSION}_linux_${TARGETARCH}.tar.gz" \
    && tar -xzf /tmp/agent.tgz -C /usr/local/bin tracewick-agent \
    && chmod 0755 /usr/local/bin/tracewick-agent \
    && rm -f /tmp/agent.tgz \
    && (getent group 33 >/dev/null || groupadd -g 33 www-data) \
    && (id -u 33 >/dev/null 2>&1 || useradd -u 33 -g 33 -M -s /usr/sbin/nologin www-data) \
    && apt-get purge -y curl \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

USER www-data:www-data
ENTRYPOINT ["tracewick-agent"]
CMD ["run", "--reader-id=bench-agent", "--sleep=2s"]

# Same runtime/UID contract, with a binary built from the exact source commit.
FROM debian:bookworm-slim AS source
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY --from=source-build /tracewick-agent /usr/local/bin/tracewick-agent
COPY --from=source-build /agent-reference /agent-reference
USER 33:33
ENTRYPOINT ["tracewick-agent"]
CMD ["run", "--reader-id=bench-agent", "--sleep=2s"]

FROM ${AGENT_BUILD_TARGET} AS final
