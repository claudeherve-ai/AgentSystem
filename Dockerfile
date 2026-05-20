# AgentSystem — Boil-the-Ocean Docker Image
# =============================================================================
# Python 3.12 + Bun + AgentSystem + slimmed claude-skills.
# Targets Azure Container Apps with Streamlit dashboard + FastAPI backend.
# =============================================================================

FROM python:3.12-slim-bookworm

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
COPY agentsystem/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY agentsystem/ .

# Copy slimmed claude-skills
COPY claude-skills-slim /app/claude-skills

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
LABEL org.opencontainers.image.description="AgentSystem Executive Hive — 36-Agent Orchestrator + 714 Claude-Skills"
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
