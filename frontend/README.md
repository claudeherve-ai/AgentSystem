# AgentSystem Mission Control

React and TypeScript operator experience for durable AgentSystem runs. The UI
creates and cancels runs, resumes persisted SSE event streams, displays real
dependency health, handles approvals, and labels unavailable backend surfaces as
not configured instead of inventing data.

## Local development

```powershell
Copy-Item .env.example .env.local
npm install
npm run dev
```

Run the API separately on the URL configured by `VITE_API_BASE_URL`.
When that variable is empty, the Vite development server proxies API and
health requests to `http://127.0.0.1:8080`.

## Configuration

| Variable | Purpose |
| --- | --- |
| `VITE_API_BASE_URL` | AgentSystem API base URL; defaults to the current origin |
| `VITE_AUTH_MODE` | `none`, `api_key`, `easy_auth`, or `entra_bearer` |
| `VITE_HEALTH_POLL_MS` | Readiness polling interval |

API keys are stored only in browser `sessionStorage`. An Entra deployment must
register a real MSAL/OAuth token callback through
`configureEntraTokenProvider`; the application never manufactures tokens.

## Validation

```powershell
npm ci
npm test
npm run lint
npm run build
```
