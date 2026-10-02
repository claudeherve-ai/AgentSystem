# syntax=docker/dockerfile:1
# =============================================================================
# AgentSystem Frontend — production image
# Static Vite/React SPA built once, served by an unprivileged nginx with a
# reverse-proxy to the internal API Container App. Publicly-routable ACA
# ingress (external) terminates TLS in front of this container; nginx itself
# listens on plain HTTP :8080 inside the managed environment.
#
# Build context is ./frontend (see azure.yaml: project: ./frontend, default
# docker.path/context).
# =============================================================================

# ---- Stage 1: build ----------------------------------------------------------
FROM node:22-alpine AS builder

WORKDIR /app

# Install dependencies first for layer caching (invalidates only when the
# lockfile changes, not on every source edit).
COPY package.json package-lock.json* ./
RUN npm ci

COPY . .

# Vite inlines VITE_-prefixed vars into the built bundle at *build* time —
# they cannot be changed at container runtime. Defaults below are safe,
# same-origin production defaults:
#   VITE_API_BASE_URL="" -> browser calls same-origin relative paths
#     (e.g. "/api/v1/..."), which nginx below reverse-proxies to the
#     internal API Container App. Avoids CORS entirely.
#   VITE_AUTH_MODE="none" -> matches the frontend's own conservative
#     fallback (frontend/src/api/auth/authProvider.ts). Override with
#     --build-arg VITE_AUTH_MODE=<api_key|easy_auth|entra_bearer> to match
#     the API's AUTH_MODE for a given environment (infra/main.bicep
#     `authMode` parameter).
#   VITE_HEALTH_POLL_MS="15000" -> in-app backend-status widget poll cadence.
ARG VITE_API_BASE_URL=""
ARG VITE_AUTH_MODE="none"
ARG VITE_HEALTH_POLL_MS="15000"
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL} \
    VITE_AUTH_MODE=${VITE_AUTH_MODE} \
    VITE_HEALTH_POLL_MS=${VITE_HEALTH_POLL_MS}

# `npm run build` runs `tsc --noEmit` then `vite build` (see package.json);
# output goes to ./dist (Vite default, unmodified by vite.config.ts).
RUN npm run build

# ---- Stage 2: runtime ---------------------------------------------------------
# nginxinc/nginx-unprivileged already runs as a non-root user (uid 101) and
# listens on unprivileged ports by default, which matches this repo's
# non-root-runtime convention without any extra USER/chown plumbing.
FROM nginxinc/nginx-unprivileged:1.27-alpine AS runtime

LABEL org.opencontainers.image.title="agentsystem-frontend" \
      org.opencontainers.image.description="AgentSystem mission-control SPA (nginx, reverse-proxied to internal API)" \
      org.opencontainers.image.source="https://github.com/claudeherve-ai/AgentSystem"

COPY --from=builder /app/dist /usr/share/nginx/html

# Templated at container start via the official nginx image's
# docker-entrypoint.sh envsubst-on-templates mechanism: substitutes only
# ${API_INTERNAL_BASE_URL} (the ACA-injected env var pointing at the internal
# API app's FQDN) into the served config, leaving nginx's own runtime
# $variables (e.g. $uri, $host) untouched.
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
ENV NGINX_ENVSUBST_FILTER=^API_INTERNAL_BASE_URL$ \
    NGINX_ENTRYPOINT_QUIET_LOGS=1

EXPOSE 8080

# Local-only probe paths (served directly by nginx, never proxied) so a
# transient API outage cannot cascade into ACA restarting the frontend
# container. See infra/modules/containerApps.bicep frontendApp probes.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1:8080/healthz/live || exit 1

# Base image's default CMD/ENTRYPOINT already runs `nginx -g "daemon off;"`
# after templating; no override needed.
