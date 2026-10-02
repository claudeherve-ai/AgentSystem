# Local development

## Prerequisites

- Python 3.12+
- Node.js 22+ and npm (for `frontend/`)
- Docker Desktop for Docker sandbox tests and container validation
- Azure CLI with Bicep only when validating Bicep locally

## Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
Copy-Item .env.template .env
python -m api.main
```

The service exposes generated OpenAPI documentation at `/docs`. The existing
application starts without an LLM provider, but chat work needs valid provider
configuration. Use `.env.template` as the field reference and never commit
your `.env`.

Start the frontend separately:

```powershell
Set-Location frontend
npm ci
npm run dev
```

## Local validation

```powershell
python -m compileall -q agents agentsystem api enforcement evals guardrails memory routing telemetry tools workflows
ruff check --select E9,F63,F7,F82 agents agentsystem api enforcement evals guardrails memory routing telemetry tools workflows tests
python -m pytest -q --cov=agentsystem --cov=api --cov=agents --cov=tools --cov=workflows --cov-fail-under=35
```

For the frontend, run `npm run lint`, `npm test`, and `npm run build` from
`frontend/`. Bicep validation is compile-time only and does not alter Azure:

```powershell
az bicep build --file infra\main.bicep
az bicep build --file infra\resources.bicep
```

Build the same four images used by CI:

```powershell
docker build --pull --file frontend\Dockerfile --tag agentsystem-frontend:local frontend
docker build --pull --file apps\api\Dockerfile --tag agentsystem-api:local .
docker build --pull --file apps\worker\Dockerfile --tag agentsystem-worker:local .
docker build --pull --file apps\operator\Dockerfile --tag agentsystem-operator:local .
```

These commands can download base images and build-time dependencies; they do
not push images or deploy anything.
