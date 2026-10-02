# syntax=docker/dockerfile:1
# =============================================================================
# AgentSystem API — production image
# Runs: uvicorn apps.api.main:app --host 0.0.0.0 --port 8080
# Serves the FastAPI composition root in api/main.py (health/readiness under
# /health/*, business routes under /api/v1/*). Internal-only ingress in ACA.
#
# Build context MUST be the repository root (see azure.yaml: project: .,
# docker.path: ./apps/api/Dockerfile) because this component imports the
# first-party packages living at the repo root (api/, agents/, routing/,
# config/, enforcement/, guardrails/, toolkits/, workflows/, telemetry/,
# evals/, skills/, agentsystem/, migrations/, apps/).
# =============================================================================

# ---- Stage 1: builder -------------------------------------------------------
FROM python:3.12-slim-bookworm AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /build

# Install build-time-only system deps needed to compile any wheels that lack
# manylinux binaries; removed entirely from the final runtime stage.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies into an isolated virtualenv first (best layer caching:
# this layer only invalidates when the lockfile changes, not on app code
# changes).
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

COPY requirements.txt requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock

# ---- Stage 2: runtime --------------------------------------------------------
FROM python:3.12-slim-bookworm AS runtime

LABEL org.opencontainers.image.title="agentsystem-api" \
      org.opencontainers.image.description="AgentSystem FastAPI backend (internal ACA ingress)" \
      org.opencontainers.image.source="https://github.com/claudeherve-ai/AgentSystem"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    PATH="/opt/venv/bin:${PATH}" \
    API_PORT=8080 \
    APP_ENV=production

# Minimal runtime OS deps: curl is intentionally NOT installed; the container
# HEALTHCHECK below uses Python's stdlib urllib instead to avoid adding an
# extra package solely for probing.
WORKDIR /app

# Bring in the prebuilt virtualenv from the builder stage (no compilers, no
# pip cache, no build-essential in the final image).
COPY --from=builder /opt/venv /opt/venv

# Application code. Build context is the repo root; .dockerignore trims
# node_modules/, frontend build output, tests, docs, and VCS metadata.
COPY . .

# Non-root runtime user, matching the repo-wide convention (uid 10001).
RUN useradd -m -u 10001 appuser \
    && mkdir -p /home/appuser/.cache \
    && chown -R appuser:appuser /app /home/appuser
USER appuser

EXPOSE 8080

# Liveness/readiness are served by api/routes/health.py at /health/live and
# /health/ready. Uses urllib (stdlib) instead of curl/wget to keep the image
# minimal.
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/health/live', timeout=3).status == 200 else 1)" || exit 1

CMD ["python", "-m", "uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8080"]
