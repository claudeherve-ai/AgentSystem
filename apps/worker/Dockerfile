# syntax=docker/dockerfile:1
# =============================================================================
# AgentSystem Worker — production image
# Runs: python -m apps.worker.main (asyncio poll loop; no HTTP server, no
# ingress). Consumes Durable Task Scheduler work items and writes results via
# managed identity.
#
# Build context MUST be the repository root (see azure.yaml: project: .,
# docker.path: ./apps/worker/Dockerfile) for the same first-party import
# reasons as apps/api/Dockerfile.
# =============================================================================

# ---- Stage 1: builder -------------------------------------------------------
FROM python:3.12-slim-bookworm AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /build

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

COPY requirements.txt requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock

# ---- Stage 2: runtime --------------------------------------------------------
FROM python:3.12-slim-bookworm AS runtime

LABEL org.opencontainers.image.title="agentsystem-worker" \
      org.opencontainers.image.description="AgentSystem durable-task worker (no ingress)" \
      org.opencontainers.image.source="https://github.com/claudeherve-ai/AgentSystem"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    PATH="/opt/venv/bin:${PATH}" \
    APP_ENV=production

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY . .

RUN useradd -m -u 10001 appuser \
    && mkdir -p /home/appuser/.cache \
    && chown -R appuser:appuser /app /home/appuser
USER appuser

# No EXPOSE/ingress: the worker is a background poll loop with no HTTP
# server. Azure Container Apps runs it with ingressEnabled: false; ACA has no
# built-in probe mechanism for non-ingress revisions, so container-level
# liveness is instead observed via process exit code / restart count and the
# Durable Task Scheduler's own work-item age alert (see infra/modules
# /alerts.bicep) rather than a Docker HEALTHCHECK.
CMD ["python", "-m", "apps.worker.main"]
