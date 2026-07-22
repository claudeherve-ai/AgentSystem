# AgentSystem

A multi-agent enterprise orchestrator built on the **Microsoft Agent Framework**.
A single orchestrator routes each request to one of **19 specialist subagents**
(email, calendar, engineering, cloud/data, security, finance, legal, sales,
product/project management, and more), each backed by real tools and optional
[MCP](https://modelcontextprotocol.io) servers.

It ships two front doors over the same orchestrator:

- **FastAPI** REST API (`api/main.py`) — chat, agent listing, health, metrics.
- **Streamlit** dashboard (`dashboard.py`) — interactive console.

---

## Quickstart (local)

Requires **Python 3.12+**.

```bash
# 1. Create + activate a virtual environment
python -m venv .venv
.venv\Scripts\activate            # Windows
# source .venv/bin/activate         # macOS/Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
copy .env.template .env             # Windows  (cp on macOS/Linux)
#   then edit .env and set ONE LLM provider (see "Environment" below)

# 4. Run the API
python -m api.main                  # serves on http://localhost:8080

# ...or the dashboard
streamlit run dashboard.py          # serves on http://localhost:8501
```

Useful endpoints once the API is up:

| Endpoint            | Purpose                          |
| ------------------- | -------------------------------- |
| `GET /health`       | Liveness / readiness probe       |
| `GET /docs`         | Swagger UI                       |
| `GET /`             | Service info + live agent list   |
| `POST /api/v1/chat` | Send a message to the orchestrator |

> **Runs without an LLM key.** The API boots, `/health` and `/docs` respond,
> and agents register even when no provider credentials are set. Chat requests
> then return a clean **503** ("No LLM provider configured") instead of a raw
> 500 — set a provider to enable responses.

---

## Quickstart (Docker)

The Docker build context is the **parent** of this folder (the image copies
`AgentSystem/` in), so build from one level up:

```bash
cd ..
docker build -t agentsystem -f AgentSystem/Dockerfile .
docker run --rm -p 8501:8501 -p 8080:8080 --env-file AgentSystem/.env agentsystem
```

The default command starts the Streamlit dashboard on **8501**; the FastAPI
backend is exposed on **8080**.

---

## Environment

Copy `.env.template` to `.env` and fill in your values. At minimum, configure
**one** LLM provider:

### LLM provider (pick one)

```dotenv
# Azure OpenAI (primary)
AZURE_OPENAI_ENDPOINT=https://YOUR-RESOURCE.cognitiveservices.azure.com/
AZURE_OPENAI_API_KEY=<your-azure-openai-key>
AZURE_OPENAI_DEPLOYMENT=gpt-4.1
AZURE_OPENAI_API_VERSION=2024-12-01-preview

# OpenAI direct (alternative)
# OPENAI_API_KEY=<your-openai-key>
```

If the provider named in `config/agents.yaml` has no usable credentials, the
orchestrator **automatically falls back** to whichever provider *does* — so
either block above is enough on its own. Placeholder values like
`<your-...-key>` are treated as "not set". Anthropic routing is stubbed and
not yet wired.

### Optional integrations

The template also documents optional credentials for Microsoft Graph
(email/calendar), Twitter/X, LinkedIn, RAG over a local `Cases` folder, and a
tiered set of MCP servers (GitHub, Microsoft Docs, Notion, Sentry, Atlassian,
filesystem, etc.). All are **opt-in** and degrade gracefully when unset.

---

## Architecture

```
                ┌──────────────┐        ┌────────────────┐
   client ───▶  │  FastAPI     │   or   │  Streamlit     │
                │  api/main.py │        │  dashboard.py  │
                └──────┬───────┘        └───────┬────────┘
                       │                        │
                       ▼                        ▼
                ┌───────────────────────────────────────┐
                │        Orchestrator (router)           │
                │   agents/orchestrator.py + factory.py  │
                └───────────────────┬───────────────────┘
                                    │ routes to one of 19
              ┌─────────────────────┼─────────────────────┐
              ▼                     ▼                     ▼
        EmailAgent          EngineeringAgent        FinanceAgent   ...
        CalendarAgent       CloudDataAgent          LegalAgent
        SocialAgent         SecurityEngineerAgent   CodeExecutorAgent
              │                     │                     │
              ▼                     ▼                     ▼
          tools / MCP servers / RAG / Microsoft Graph / web / Docker sandbox
```

- **`agents/factory.py`** registers the 19 agents and their tools.
- **`agents/orchestrator.py`** builds the model client (with provider
  fallback) and routes requests; its routing prompt lives in
  `config/agents.yaml`.
- **`config/__init__.py`** loads and validates configuration, detecting
  placeholder credentials so the app degrades gracefully.

---

## Sandboxed code execution

`CodeExecutorAgent` runs untrusted Python in a **hardened, ephemeral Docker
container** instead of the host. Each run gets a fresh container that is:

- **network-isolated** (`--network none` — no outbound calls),
- **read-only root** with a small writable `tmpfs` `/tmp`,
- **non-root** (`--user 65534:65534`), `--cap-drop ALL`, `no-new-privileges`,
- **resource-bounded** (memory, CPUs, PID count, output size, wall-clock
  timeout), and
- **auto-reaped** — stale sandbox containers are cleaned up on startup.

Control it via `.env` (see `.env.template` → *Code Sandbox*):

```bash
CODE_SANDBOX_MODE=auto   # auto | docker | subprocess | off
SANDBOX_IMAGE=python:3.12-slim
SANDBOX_TIMEOUT=30
SANDBOX_MEMORY=256m
```

**Graceful degradation:** when the Docker daemon is unreachable (and mode is
`auto`), execution falls back to a local subprocess that is clearly labelled
`engine: subprocess · NOT isolated` in its output header, so callers always
know whether the result came from a sandbox. Set `CODE_SANDBOX_MODE=docker` to
require isolation, or `off` to disable code execution entirely. No extra Python
package is needed — the sandbox shells out to the Docker CLI.

---

## Self-observability (tracing)

The app records **in-process spans** for incoming requests, orchestrator
routing, agent turns, and tool calls — no external collector required. Inspect
them live over HTTP:

```bash
# Recent spans (newest first; limit 1..500)
curl http://localhost:8000/api/v1/observability/traces?limit=50

# Tracer stats (enabled flags, buffered span count, exporters)
curl http://localhost:8000/api/v1/observability/stats
```

Configure via `.env` (see `.env.template` → *Self-Observability*):

```bash
TELEMETRY_ENABLED=true
TELEMETRY_CAPTURE_CONTENT=false   # off by default (PII risk)
OBSERVABILITY_API_ENABLED=true    # endpoints return 404 when false
TELEMETRY_MAX_SPANS=500           # ring-buffer size
```

Telemetry is **dependency-free** and sanitizes attributes (sensitive keys
redacted, content omitted unless `TELEMETRY_CAPTURE_CONTENT=true`). Optional
external backends — OTLP (`OTEL_EXPORTER_OTLP_ENDPOINT`) and Langfuse
(`LANGFUSE_*`) — are wired but inert until you set their credentials and
uncomment the matching extras in `requirements.txt`.

---

## Tests

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest tests/test_smoke.py -q
```

CI runs the same smoke suite on every push/PR (see
`.github/workflows/ci.yml`). Linting (`ruff`) runs non-blocking; tests are
required to pass.

---

## Security notes

- Set `AUTH_ENABLED=true` to require an API key (`API_KEY`) on requests; auth
  fails **closed** if enabled but misconfigured.
- Set `CORS_ORIGINS` to an explicit comma-separated allow-list in production;
  the default `*` disables credentialed CORS (per browser rules).
- Never commit `.env` — it is git-ignored.
