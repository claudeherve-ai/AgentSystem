# syntax=docker/dockerfile:1
# =============================================================================
# AgentSystem Operator Console — production image
# Runs: streamlit run dashboard.py (Streamlit UI at repo root; zero
# first-party imports — only os/typing/requests/streamlit). Internal-only
# ingress, scale-to-zero (min replicas 0) in ACA.
#
# Build context is the repository root (dashboard.py must not be relocated —
# out of scope for this task), shared with apps/api and apps/worker. The
# repo-root .dockerignore trims node_modules/, frontend build output, tests,
# and docs from the context sent to the daemon. This Dockerfile only ever
# COPYs the three files it needs (dashboard.py + manifests), so unrelated
# context bloat affects build-context transfer time only, never final image
# size or contents.
# =============================================================================

# ---- Stage 1: builder -------------------------------------------------------
FROM python:3.12-slim-bookworm AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /build

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

# Use the monorepo lockfile as a *constraints* file (-c), not a requirements
# file (-r): this pins streamlit/requests to the exact versions already
# resolved for the rest of the monorepo without installing the full heavy
# dependency graph (agent-framework-core, msal, azure-identity, etc.) that
# the operator console never imports. pip's constraints-file parser rejects
# extras syntax (e.g. "uvicorn[standard]==...", "httpx[brotli,...]==..."),
# so those lines are stripped into a filtered copy first; none of the
# packages using extras are needed by this image.
COPY requirements.lock ./
RUN grep -v '\[' requirements.lock > constraints.txt \
    && pip install --no-cache-dir -c constraints.txt streamlit requests

# ---- Stage 2: runtime --------------------------------------------------------
FROM python:3.12-slim-bookworm AS runtime

LABEL org.opencontainers.image.title="agentsystem-operator" \
      org.opencontainers.image.description="AgentSystem operator console (Streamlit, internal ingress, scale-to-zero)" \
      org.opencontainers.image.source="https://github.com/claudeherve-ai/AgentSystem"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:${PATH}" \
    APP_ENV=production \
    STREAMLIT_SERVER_FILE_WATCHER_TYPE=none \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    STREAMLIT_SERVER_HEADLESS=true

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv

# Only the operator console script and its (unused-at-runtime, kept for
# provenance) dependency manifests are copied — not the rest of the
# repository, regardless of what else is present in the build context.
COPY dashboard.py requirements.txt requirements.lock ./

RUN useradd -m -u 10001 appuser \
    && chown -R appuser:appuser /app /home/appuser
USER appuser

EXPOSE 8501

# Streamlit's built-in health endpoint.
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=3).status == 200 else 1)" || exit 1

CMD ["streamlit", "run", "dashboard.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
