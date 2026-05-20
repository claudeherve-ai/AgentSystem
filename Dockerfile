# AgentSystem — Boil-the-Ocean Docker Image
# =============================================================================
# Multi-stage build:
#   Stage 1 (skills-src): Slim claude-skills (SKILL.md + scripts only)
#   Stage 2 (app): Python 3.12 + Bun + AgentSystem + claude-skills
# Targets Azure Container Apps with Streamlit dashboard + FastAPI backend.
# =============================================================================

# ── Stage 1: Slim claude-skills ─────────────────────────────────────────────
FROM python:3.12-slim-bookworm AS skills-src
RUN apt-get update && apt-get install -y rsync && rm -rf /var/lib/apt/lists/*
# claude-skills is expected at build context root or mounted
# Only copy SKILL.md, scripts/*.py, references/*.md — exclude .git, assets, docs
COPY claude-skills/ /tmp/claude-skills-full/
RUN mkdir -p /tmp/claude-skills-slim && \
    (find /tmp/claude-skills-full -name "SKILL.md" -exec dirname {} \; | sort -u | while read d; do \
        mkdir -p "/tmp/claude-skills-slim/${d#/tmp/claude-skills-full/}"; \
        cp "$d/SKILL.md" "/tmp/claude-skills-slim/${d#/tmp/claude-skills-full/}/" 2>/dev/null; \
        cp -r "$d/scripts" "/tmp/claude-skills-slim/${d#/tmp/claude-skills-full/}/" 2>/dev/null; \
        cp -r "$d/references" "/tmp/claude-skills-slim/${d#/tmp/claude-skills-full/}/" 2>/dev/null; \
    done) 2>/dev/null; \
    echo "Skills slimmed: $(find /tmp/claude-skills-slim -name 'SKILL.md' | wc -l) SKILL.md files"

# ── Stage 2: Application ────────────────────────────────────────────────────
FROM python:3.12-slim-bookworm AS app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl unzip git build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Bun (for GStack workflow)
ENV BUN_INSTALL="/root/.bun"
ENV PATH="$BUN_INSTALL/bin:$PATH"
RUN curl -fsSL https://bun.sh/install | bash

WORKDIR /app

# Copy and install Python dependencies (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Copy slim claude-skills from stage 1
COPY --from=skills-src /tmp/claude-skills-slim /app/claude-skills

# Ensure runtime directories exist
RUN mkdir -p /app/memory /app/logs /app/config

# Environment
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV PORT=8501
ENV APP_ENV=production

# Expose Streamlit (8501) and FastAPI (8080)
EXPOSE 8501 8080

# Labels
LABEL org.opencontainers.image.source="https://github.com/claudeherve-ai/AgentSystem"
LABEL org.opencontainers.image.description="AgentSystem Executive Hive — 36-Agent Orchestrator + Claude-Skills"
LABEL org.opencontainers.image.title="AgentSystem"

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Default: Streamlit dashboard
CMD ["streamlit", "run", "dashboard.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--browser.serverAddress=0.0.0.0"]
