"""
AgentSystem — Agent Management Routes
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from api.main import get_orchestrator

router = APIRouter()


class AgentInfo(BaseModel):
    name: str
    description: str | None
    registered: bool


@router.get("/", response_model=list[AgentInfo])
async def list_agents():
    """List all registered agents with their descriptions."""
    orch = get_orchestrator()
    # Build descriptions from registrations (internal dict)
    return [
        {
            "name": name,
            "description": orch._registrations.get(name, {}).description
            if hasattr(orch._registrations.get(name, {}), "description")
            else f"Agent: {name}",
            "registered": name in orch.agent_names,
        }
        for name in orch.agent_names
    ]


@router.get("/count")
async def agent_count():
    """Return total agent count."""
    orch = get_orchestrator()
    return {
        "total_agents": len(orch.agent_names),
        "agents": orch.agent_names,
    }


@router.get("/{agent_name}")
async def get_agent(agent_name: str):
    """Get details about a specific agent."""
    orch = get_orchestrator()
    if agent_name not in orch.agent_names:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")

    registration = orch._registrations.get(agent_name)
    agent = orch.get_agent(agent_name)

    return {
        "name": agent_name,
        "description": registration.description if registration else None,
        "tool_count": len(registration.tools) if registration else 0,
        "instantiated": agent is not None,
    }


@router.get("/{agent_name}/tools")
async def get_agent_tools(agent_name: str):
    """List tools available to a specific agent."""
    orch = get_orchestrator()
    if agent_name not in orch.agent_names:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")

    registration = orch._registrations.get(agent_name)
    if not registration:
        return {"tools": []}

    tools_info = []
    for tool in registration.tools:
        tool_info = {
            "name": getattr(tool, "__name__", str(tool)),
        }
        if hasattr(tool, "__doc__") and tool.__doc__:
            tool_info["description"] = tool.__doc__.strip().split("\n")[0]
        tools_info.append(tool_info)

    return {"agent": agent_name, "tool_count": len(tools_info), "tools": tools_info}


@router.get("/status")
async def orchestrator_status():
    """Full orchestrator status dump."""
    orch = get_orchestrator()
    return orch.status()
