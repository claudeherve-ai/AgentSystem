"""
AgentSystem — OpenAI Realtime voice adapter (PR5, OPTIONAL / FAIL-CLOSED).

A thin, fully-optional helper that produces the *configuration descriptor* for
an OpenAI Realtime (voice) session. It deliberately performs **no network call**
and **never echoes the API key**, so it is safe to import, register, and exercise
in CI with no credentials.

Design contract (mirrors :mod:`tools.azure_search` exactly):

  * The ``openai`` SDK is imported behind a guarded ``try``. If it is absent the
    module still imports cleanly and simply reports "disabled".
  * Voice is enabled only when BOTH the SDK is importable AND
    :func:`config.get_voice_config` reports ``enabled`` (explicit
    ``VOICE_ENABLED=true`` flag AND a real, non-placeholder ``OPENAI_API_KEY``).
  * :func:`create_realtime_session` returns a plain ``dict`` describing the
    session a browser/client would open against the OpenAI Realtime API, or
    ``None`` when voice is disabled. It NEVER raises and NEVER returns the key.

The actual realtime audio stream is negotiated client-side directly with OpenAI
using an ephemeral token the *application* would mint; exposing the long-lived
key here would be a security defect, so this adapter intentionally returns only
the non-secret session parameters.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ── Guarded SDK import ───────────────────────────────────────────────────────
try:  # pragma: no cover - exercised only when the optional SDK is installed
    import openai  # noqa: F401

    _SDK_AVAILABLE = True
except Exception:  # noqa: BLE001 - any import problem => feature simply off
    openai = None  # type: ignore[assignment]
    _SDK_AVAILABLE = False

# Log a disabled-because-of-failure warning at most once per process.
_WARNED = False

# Modalities the demo realtime session advertises. Audio + text is the default
# realtime conversation shape.
_MODALITIES = ["audio", "text"]


def sdk_available() -> bool:
    """True if the optional ``openai`` SDK is importable."""
    return _SDK_AVAILABLE


def voice_enabled() -> bool:
    """True only when the SDK is present AND voice is configured + opted-in."""
    if not _SDK_AVAILABLE:
        return False
    try:
        from config import get_voice_config

        return bool(get_voice_config().enabled)
    except Exception as exc:  # noqa: BLE001 - config issues => disabled
        logger.debug("voice_enabled: config load failed (%s)", exc)
        return False


def voice_status() -> dict[str, Any]:
    """Diagnostic snapshot — never exposes the API key."""
    status: dict[str, Any] = {
        "sdk_available": _SDK_AVAILABLE,
        "enabled": False,
        "model": None,
        "voice": None,
        "modalities": list(_MODALITIES),
    }
    try:
        from config import get_voice_config

        cfg = get_voice_config()
        status["enabled"] = bool(cfg.enabled and _SDK_AVAILABLE)
        status["model"] = cfg.model
        status["voice"] = cfg.voice
    except Exception as exc:  # noqa: BLE001
        logger.debug("voice_status: config load failed (%s)", exc)
    return status


def _warn_once(msg: str, *args: Any) -> None:
    global _WARNED
    if not _WARNED:
        logger.warning(msg, *args)
        _WARNED = True


def create_realtime_session(instructions: Optional[str] = None) -> Optional[dict[str, Any]]:
    """Return the non-secret descriptor for an OpenAI Realtime session.

    Returns ``None`` when voice is disabled (SDK missing, flag off, or only a
    placeholder key). When enabled, returns a dict with the model, voice,
    modalities, and optional system ``instructions`` — but **never** the API
    key, and **without** making any network call. The function never raises.
    """
    if not voice_enabled():
        return None
    try:
        from config import get_voice_config

        cfg = get_voice_config()
        descriptor: dict[str, Any] = {
            "model": cfg.model,
            "voice": cfg.voice,
            "modalities": list(_MODALITIES),
        }
        if instructions:
            descriptor["instructions"] = str(instructions)
        return descriptor
    except Exception as exc:  # noqa: BLE001 - any failure => disabled, never raise
        _warn_once("create_realtime_session failed, voice disabled (%s)", exc)
        return None
