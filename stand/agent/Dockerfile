# Thin image: public GitHub release binary (avoids private GHCR pulls).
# Runs as UID/GID 33 to match PHP-FPM www-data on the spool volume.
FROM debian:bookworm-slim

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
