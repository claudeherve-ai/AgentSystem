# AgentSystem — Boil the Ocean Improvement Plan
## May 20, 2026

### PHASE 1: CRITICAL FIXES (Immediate)

#### 1.1 Fix Cloud Factory Bug [P0]
**Problem:** `dashboard.py` imports `from agents.factory import build_orchestrator` which only registers EmailAgent. Cloud shows "1 Agent Registered."
**Fix:** Rewrite `agents/factory.py` to call `main.build_orchestrator()` so cloud gets all 38 agents.

#### 1.2 Fix Dockerfile [P0]
- Wrong label references `alirezarezvani/claude-skills` → fix to `claudeherve-ai/AgentSystem`
- CMD launches `main.py` but cloud runs Streamlit → add proper entrypoint script
- Add health-check endpoint for ACA

### PHASE 2: ARCHITECTURAL UPGRADES (This Week)

#### 2.1 FastAPI Backend Layer
New `api/` directory with:
- `api/main.py` — FastAPI app with /health, /agents, /chat endpoints
- `api/routes/agents.py` — List agents, get status, invoke specific agent
- `api/middleware/auth.py` — API key + optional OAuth
- Streamlit dashboard becomes UI layer on top of FastAPI

#### 2.2 Agent Intelligence Upgrade
Current agents are templates returning hardcoded strings. Replace with:
- Each agent gets real LLM-powered reasoning
- Multi-turn conversation within agent scope
- Agent-specific tool chains (web search, file read, code execution)
- Inter-agent handoff protocol

#### 2.3 Skills Integration Bridge
Bridge the 313+ claude-skills and awesome-claude-code-plugins skills:
- `skills/bridge.py` — Skill loader that maps external skills to agent tools
- Priority skills to integrate:
  - C-level advisory (CEO, CTO, CFO, CMO, CISO, CPO)
  - Engineering powerful (code review, debugging, API design)
  - Regulatory compliance (GDPR, SOC2, ISO 27001, MDR)
  - Research (arxiv, web search, paper analysis)
  - DevOps (CI/CD, Docker, Kubernetes, Azure)

### PHASE 3: ENTERPRISE READINESS

#### 3.1 Security Layer
- JWT/OAuth authentication on API
- Rate limiting per client
- Audit logging for all agent actions
- Content safety filters
- RBAC for agent access

#### 3.2 Multi-Model Support
- Add Anthropic Claude provider
- Add local model support (Ollama, llama.cpp)
- Add model fallback chain
- Per-agent model selection

#### 3.3 Agent Coordination Protocol
- Multi-agent workflow definition (DAG of agent calls)
- Shared context between collaborating agents
- Result aggregation and conflict resolution
- Human-in-the-loop approval gates

### PHASE 4: OBSERVABILITY & RELIABILITY

#### 4.1 Monitoring
- Prometheus metrics for agent latency, success rate
- Azure Application Insights integration
- Cost tracking per agent invocation

#### 4.2 Testing Framework
- Agent evaluation suite (correctness, relevance, safety)
- Regression tests for agent behavior
- Load testing for concurrent agent requests

### SKILLS TO INTEGRATE (Priority Order)

1. `c-level-advisory` — Full C-suite strategic agents
2. `engineering-powerful` — Advanced engineering skills  
3. `regulatory-compliance` — GDPR, SOC2, ISO, FDA, MDR
4. `devops` — CI/CD, Azure, Docker, Kubernetes
5. `research` — Academic, web, market research
6. `social-media` — X/Twitter, content creation
7. `creative` — Diagrams, infographics, ASCII art
8. `security` — Red-teaming, vulnerability scanning

### FILES TO CREATE/MODIFY

| File | Action | Priority |
|------|--------|----------|
| `agents/factory.py` | REPLACE — use main.build_orchestrator | P0 |
| `Dockerfile` | FIX — labels, entrypoint, health | P0 |
| `api/main.py` | CREATE — FastAPI backend | P1 |
| `api/routes/agents.py` | CREATE — Agent API routes | P1 |
| `api/middleware/auth.py` | CREATE — Auth middleware | P1 |
| `skills/bridge.py` | CREATE — Skills integration | P1 |
| `dashboard.py` | UPDATE — Connect to FastAPI backend | P1 |
| `config/models.yaml` | CREATE — Multi-model config | P2 |
| `tests/eval_suite.py` | CREATE — Agent evaluation | P2 |
| `start.sh` | CREATE — Unified entrypoint script | P0 |
