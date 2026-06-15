---
title: "AgentSystem Upgrade — Boil the Ocean Implementation Plan"
created: 2026-06-15
status: in_progress
---

# AgentSystem Upgrade Plan

## Unified Diagnosis

Two feedback streams merged:

| Source | Lens | Core Finding |
|--------|------|-------------|
| Cloud agent self-assessment | Behavioral quality | "Sometimes genius, sometimes pretty good." Rules exist but aren't enforced. |
| Infrastructure analysis | Capability gaps | No messaging ingress, no Hermes sidecar, no shared memory. |

The orchestrator already has grounding directives, auto-critique, plan/project tools, and 18+ MCP integrations. The gap is that these are *encouraged* not *enforced*, creating variance.

## What Already Works (Don't Touch)

- GROUNDING_DIRECTIVE — 7-point mandatory grounding gate ✓
- BOIL_THE_OCEAN_DIRECTIVE — Operating standard ✓
- Auto-critique (`_maybe_auto_critique`, `should_auto_critique`) ✓
- Plan/project tools wired to orchestrator ✓
- Memory tools (durable memory, session context) ✓
- Email/Calendar agents working (delegated auth) ✓
- 18 specialist agents registered ✓
- MCP tools: Docs, GitHub, DeepWiki, Context7, HuggingFace, Notion, Sentry, Atlassian ✓
- Model routing with fallback chains ✓
- Content filter auto-recovery ✓

## What We're Changing

### Phase 1: Hardened Operational Discipline
**Goal**: Turn encouragement into enforcement. Rules should be non-negotiable defaults, not suggestions.

**Changes**:
1. Add `ROUTING_GATE` to orchestrator — must classify task type before routing
2. Add `GROUNDING_CHECK` post-specialist — verify specialist used required tools
3. Add `COMPLETION_AUDIT` — verify the task was actually completed, not just advised
4. Add `EVIDENCE_CITATION` standard — grounded answers must show sources

### Phase 2: Specialist Scorecards + Evals
**Goal**: Define what "good" means per specialist with benchmark tasks.

**Changes**:
1. Create `config/specialist_scorecards.yaml` — per-agent quality standards
2. Create `evals/specialist_benchmarks.py` — benchmark tasks per agent
3. Add eval runner that scores specialist outputs

### Phase 3: Infrastructure Expansion
**Goal**: Add messaging, Hermes runtime, shared memory.

**Changes**:
1. Add OpenClaw sidecar to Dockerfile
2. Add Hermes Agent runtime sidecar  
3. Add GBrain client integration
4. Fix inotify limit

## Implementation Order

Phase 1 → Phase 2 → Phase 3 → Test → Deploy → Commit

Each phase: implement, test locally, verify.
