"""
AgentSystem — Voice (OpenAI Realtime) Routes (PR5, OPTIONAL / FAIL-CLOSED).

REST surface over the optional voice adapter (:mod:`tools.voice`). Voice is OFF
by default and only turns on when BOTH the ``openai`` SDK is importable AND
``VOICE_ENABLED=true`` is set alongside a real (non-placeholder)
``OPENAI_API_KEY``.

Endpoints (mounted under ``/api/v1/voice``):
    GET  /status     Adapter availability snapshot (never exposes the key).
    POST /session    Mint the non-secret descriptor for a realtime session.

When voice is disabled, ``POST /session`` returns a clean **503** rather than a
raw 500. No network call is ever made and the API key is never returned.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from tools import voice

router = APIRouter()


class SessionRequest(BaseModel):
    """Optional body for a realtime session: a system instruction string."""

    instructions: str | None = None


@router.get("/status")
async def voice_status():
    """Return the voice adapter availability snapshot (no secrets)."""
    return voice.voice_status()


@router.post("/session")
async def create_session(request: SessionRequest | None = None):
    """Return the non-secret descriptor for an OpenAI Realtime session.

    Returns 503 when voice is disabled (SDK missing, flag off, or only a
    placeholder key).
    """
    instructions = request.instructions if request else None
    descriptor = voice.create_realtime_session(instructions=instructions)
    if descriptor is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Voice is disabled. Set VOICE_ENABLED=true and a real "
                "OPENAI_API_KEY (with the openai SDK installed) to enable it."
            ),
        )
    return descriptor
