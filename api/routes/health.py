"""
AgentSystem — Health Routes
"""
from fastapi import APIRouter
from api.dependencies import get_orchestrator

router = APIRouter()


@router.get("/health", include_in_schema=True)
async def health_check():
    """Kubernetes/ACA-compatible health endpoint."""
    orch = get_orchestrator()
    
    # ── Skills health ──────────────────────────────────────────────────
    skills_status = {"status": "unknown", "count": 0, "domains": 0}
    try:
        from skills.claude_skills_integration import discover_claude_skills, CLAUDE_SKILLS_ROOT
        inventory = discover_claude_skills()
        total = sum(len(skills) for skills in inventory.values())
        skills_status = {
            "status": "healthy" if total >= 100 else "degraded",
            "path": str(CLAUDE_SKILLS_ROOT),
            "exists": CLAUDE_SKILLS_ROOT.exists(),
            "count": total,
            "domains": len(inventory),
        }
    except Exception as e:
        skills_status = {"status": "error", "error": str(e)}
    
    return {
        "status": "healthy",
        "agents_registered": len(orch.agent_names),
        "agents": orch.agent_names,
        "skills": skills_status,
    }


@router.get("/readiness")
async def readiness():
    """Readiness probe — verifies orchestrator is initialized."""
    try:
        orch = get_orchestrator()
        return {"ready": True, "agents": len(orch.agent_names)}
    except Exception as e:
        return {"ready": False, "error": str(e)}


@router.get("/live")
async def liveness():
    """Liveness probe — minimal check."""
    return {"alive": True}
