"""
AgentSystem — Health Routes
"""
from fastapi import APIRouter
from api.main import get_orchestrator

router = APIRouter()


@router.get("/health", include_in_schema=True)
async def health_check():
    """Kubernetes/ACA-compatible health endpoint."""
    orch = get_orchestrator()
    return {
        "status": "healthy",
        "agents_registered": len(orch.agent_names),
        "agents": orch.agent_names,
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
