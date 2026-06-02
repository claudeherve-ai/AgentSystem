"""
AgentSystem — Chat Routes

Main conversational interface for interacting with the multi-agent orchestrator.
Supports streaming and synchronous modes.
"""
import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from api.dependencies import get_orchestrator
from config import MissingModelCredentialsError, get_model_config

logger = logging.getLogger("agentsystem.api.chat")
router = APIRouter()


class ChatRequest(BaseModel):
    message: str = Field(..., description="The user's message to route to agents")
    session_id: Optional[str] = Field(None, description="Session ID for conversation continuity")
    preferred_agent: Optional[str] = Field(None, description="Route to a specific agent directly")
    stream: bool = Field(False, description="Stream the response token-by-token")


class ChatResponse(BaseModel):
    response: str
    session_id: str
    agents_used: list[str] = []


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Send a message to the orchestrator and get a response.

    The orchestrator automatically routes to the appropriate specialist agent(s)
    based on the message content and intent classification.
    """
    orch = get_orchestrator()
    logger.info("Chat request: %.100s... (stream=%s)", request.message, request.stream)

    try:
        # If preferred_agent is specified, route directly
        if request.preferred_agent:
            agent = orch.get_agent(request.preferred_agent)
            if not agent:
                raise HTTPException(
                    status_code=404,
                    detail=f"Agent '{request.preferred_agent}' not found",
                )
            # TODO: direct agent invocation
            response = await orch.route_task(
                f"[Direct to {request.preferred_agent}]: {request.message}"
            )
            return ChatResponse(
                response=response,
                session_id=orch._active_session_id,
                agents_used=[request.preferred_agent],
            )

        # Standard orchestrator routing
        response = await orch.route_task(request.message)

        return ChatResponse(
            response=response,
            session_id=orch._active_session_id,
            agents_used=[],  # The coordinator determines which agents are called
        )

    except HTTPException:
        # Preserve intentional HTTP errors (e.g. 404 unknown agent).
        raise
    except MissingModelCredentialsError as e:
        logger.warning("Chat unavailable — no LLM provider configured: %s", e)
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error("Chat error: %s", e)
        raise HTTPException(status_code=500, detail="Internal error routing chat request.")


@router.post("/stream")
async def chat_stream(request: ChatRequest):
    """Stream a chat response (SSE format)."""
    orch = get_orchestrator()

    # Fail fast with a real HTTP status when no provider is usable, rather than
    # leaking an error inside a 200 OK event stream.
    model_cfg = get_model_config()
    if not model_cfg.has_any_model_credentials:
        raise HTTPException(
            status_code=503,
            detail=(
                "No LLM provider is configured. Set AZURE_OPENAI_ENDPOINT + "
                "AZURE_OPENAI_API_KEY, or OPENAI_API_KEY, in your .env."
            ),
        )

    async def event_generator():
        try:
            response = await orch.route_task(request.message)
            # Split response into chunks for streaming effect
            words = response.split()
            for i in range(0, len(words), 5):
                chunk = " ".join(words[i : i + 5])
                yield f"data: {chunk}\n\n"
                await asyncio.sleep(0.05)
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error("Chat stream error: %s", e)
            yield "data: [ERROR] Internal error generating response.\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/session/new")
async def new_session():
    """Start a fresh conversation session while keeping durable memory."""
    orch = get_orchestrator()
    new_id = orch.reset_session()
    return {"session_id": new_id, "message": "New session started. Durable memory preserved."}


@router.get("/session/{session_id}")
async def get_session(session_id: str):
    """Get session info."""
    orch = get_orchestrator()
    return {
        "session_id": session_id,
        "active_session": orch._active_session_id,
        "match": session_id == orch._active_session_id,
    }
