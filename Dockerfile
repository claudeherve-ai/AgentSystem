# AgentSystem — Boil-the-Ocean Docker Image
# =============================================================================
# Python 3.12 + Bun + AgentSystem + slimmed claude-skills.
# Targets Azure Container Apps with Streamlit dashboard + FastAPI backend.
# =============================================================================

FROM python:3.12-slim-bookworm

# Install system dependencies (shared libs for Chromium)
RUN apt-get update && apt-get install -y \
    curl unzip git build-essential \
    libasound2 libatk-bridge2.0-0 libatk1.0-0 \
    libcups2 libdrm2 libgbm1 libnss3 libxcomposite1 \
    libxdamage1 libxkbcommon0 libxrandr2 xdg-utils \
    fonts-liberation libu2f-udev libvulkan1 \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 22.x (for browse CLI)
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install browse.sh CLI (browser tools for agents)
RUN npm install -g browse

# ── OpenClaw (messaging gateway) ──────────────────────────────────────
# Enables inbound Telegram/WhatsApp/Discord messaging.
# Configured via OPENCLAW_API_URL / OPENCLAW_BRIDGE_PORT env vars.
RUN npm install -g openclaw

# Install xurl CLI (official X/Twitter API client)
RUN curl -fsSL https://raw.githubusercontent.com/xdevplatform/xurl/main/install.sh | bash

# Install Chromium via Playwright (avoids Debian Bookworm snap-wrapper issue)
RUN npx playwright install chromium
# browse_tools.py auto-discovers Playwright Chromium path at runtime
ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true

# Install Bun (for GStack workflow)
ENV BUN_INSTALL="/root/.bun"
ENV PATH="$BUN_INSTALL/bin:$PATH"
RUN curl -fsSL https://bun.sh/install | bash

# ── GBrain (cross-system knowledge graph) ─────────────────────────────
# Installed via Bun from the canonical repo so the cloud can query the
# same knowledge graph as local Hermes. Auth via env vars.
RUN bun install -g github:garrytan/gbrain

WORKDIR /app

# Copy and install Python dependencies (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Hermes Agent sidecar (MCP tools, 91 MS security skills, cron) ─────
# Enables multi-model agent orchestration as a companion to AgentSystem.
RUN pip install --no-cache-dir hermes-agent
# hermes-agent 0.19.0 pins openai==2.24.0, which LACKS ResponseToolSearchCall
# that agent-framework-openai needs (symbol exists only in openai 2.25–2.36).
# Re-assert our pin after the sidecar install.
RUN pip install --no-cache-dir 'openai==2.25.0'

# Copy AgentSystem application code
COPY . .

# Copy slimmed claude-skills (pre-built by scripts/build-claude-skills-slim.sh)
# Run the script first: ./scripts/build-claude-skills-slim.sh .
COPY claude-skills-slim/ /app/claude-skills/

# ═══ VERIFICATION: Warn if skills are missing ═══
RUN SKILL_COUNT=$(find /app/claude-skills -name "SKILL.md" 2>/dev/null | wc -l) && \
    echo "claude-skills: ${SKILL_COUNT} SKILL.md files baked into image" && \
    if [ "$SKILL_COUNT" -lt 100 ]; then \
        echo "⚠️  Only ${SKILL_COUNT} SKILL.md files (expected 300+)"; \
    else \
        echo "✅ Skills verification: ${SKILL_COUNT} skills ready"; \
    fi

# Ensure runtime directories exist
RUN mkdir -p /app/memory /app/logs /app/config

# Environment
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV PORT=8501
ENV APP_ENV=production
# Disable Streamlit file watcher in container (avoids inotify limit errors
# with 300+ skills files). Not needed — container images are immutable.
ENV STREAMLIT_SERVER_FILE_WATCHER_TYPE=none

# ── Non-root runtime user ─────────────────────────────────────────────
# Streamlit + FastAPI don't need root. Playwright chromium and all deps
# are already installed system-wide above.
RUN useradd -m -u 10001 appuser \
    && mkdir -p /home/appuser/.cache \
    && cp -r /root/.cache/ms-playwright /home/appuser/.cache/ms-playwright \
    && chmod +x /app/scripts/docker-entrypoint.sh \
    && chown -R appuser:appuser /app /home/appuser
USER appuser

# Expose Streamlit (8501) and FastAPI (8080 — /health /readiness /live)
EXPOSE 8501 8080

# Labels
LABEL org.opencontainers.image.source="https://github.com/claudeherve-ai/AgentSystem"
LABEL org.opencontainers.image.description="AgentSystem — Multi-Agent Enterprise Orchestrator with Claude Skills"
LABEL org.opencontainers.image.title="AgentSystem"

# Health check (Streamlit web tier; FastAPI /health checked by ACA probes)
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Default: launcher runs both Streamlit (8501) and FastAPI (8080)
CMD ["/app/scripts/docker-entrypoint.sh"]
