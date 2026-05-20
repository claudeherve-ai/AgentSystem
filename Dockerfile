# Stage 1: Runtime and System Dependencies
FROM python:3.12-slim-bookworm AS base

# Install system dependencies including curl for bun installation
RUN apt-get update && apt-get install -y \
    curl \
    unzip \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Bun (Mandatory for GStack workflow)
ENV BUN_INSTALL="/root/.bun"
ENV PATH="$BUN_INSTALL/bin:$PATH"
RUN curl -fsSL https://bun.sh/install | bash

# Stage 2: Python Environment Setup
WORKDIR /app

# Copy requirement files first for better caching
COPY requirements.txt .
# If you have a package.json for bun, uncomment below:
# COPY package.json bun.lockb* ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Ensure standard directories exist for AgentSystem
RUN mkdir -p /app/memory /app/logs /app/config

# Set Environment Variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8080
ENV APP_ENV=production

# Expose ports for both possible use cases (FastAPI backend or Streamlit dashboard)
EXPOSE 8080 8501

# Default label for Azure Container Apps
LABEL org.opencontainers.image.source="https://github.com/alirezarezvani/claude-skills"
LABEL description="AgentSystem Executive Hive - 38 Agent Orchestrator with Bun/GStack support"

# The command is overridden by azure.yaml entrypoints, but provide a default for safety
CMD ["python", "main.py"]
