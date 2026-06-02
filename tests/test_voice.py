"""
Tests for the optional voice feature (PR5):
  * tools/voice.py          — OpenAI Realtime adapter (fail-closed, no network).
  * api/routes/voice.py     — REST surface (status / session).

Voice is OFF by default and only turns on when BOTH the ``openai`` SDK is
importable AND ``VOICE_ENABLED=true`` is set alongside a real (non-placeholder)
``OPENAI_API_KEY``. These tests assert the fail-closed default with NO
credentials, and exercise the enabled path by monkeypatching the config getter
(never a real key, never a network call). The API key is never echoed by any
surface.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import VoiceConfig
from tools import voice

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
except Exception:  # pragma: no cover - httpx missing
    FastAPI = None  # type: ignore[assignment]
    TestClient = None  # type: ignore[assignment]


_REAL_KEY = "sk-live-abc123def456ghi789"


def _enabled_cfg() -> VoiceConfig:
    """A config that reports ``enabled`` without ever using a real key."""
    return VoiceConfig(
        api_key=_REAL_KEY,
        model="gpt-4o-realtime-preview",
        voice="alloy",
        flag_enabled=True,
    )


# ── adapter: fail-closed default ─────────────────────────────────────────────


def test_status_fail_closed_default(monkeypatch):
    # Force a disabled config so the test does not depend on ambient env.
    monkeypatch.setattr(
        "config.get_voice_config",
        lambda: VoiceConfig(api_key="", flag_enabled=False),
    )
    status = voice.voice_status()
    assert status["enabled"] is False
    # The key must NEVER appear in the status surface, under any field.
    assert "api_key" not in status
    assert _REAL_KEY not in str(status.values())
    print("✅ voice status fail-closed, no key")


def test_session_returns_none_when_disabled(monkeypatch):
    monkeypatch.setattr(
        "config.get_voice_config",
        lambda: VoiceConfig(api_key="", flag_enabled=False),
    )
    assert voice.create_realtime_session("say hi") is None
    assert voice.voice_enabled() is False
    print("✅ session None when disabled")


def test_placeholder_key_stays_disabled(monkeypatch):
    # Flag flipped on but key is a placeholder => still fail-closed.
    monkeypatch.setattr(
        "config.get_voice_config",
        lambda: VoiceConfig(api_key="<your-openai-key>", flag_enabled=True),
    )
    assert voice.voice_enabled() is False
    assert voice.create_realtime_session() is None
    print("✅ placeholder key stays disabled")


def test_create_session_never_raises(monkeypatch):
    # A config getter that explodes must degrade to None, never propagate.
    def _boom():
        raise RuntimeError("config blew up")

    monkeypatch.setattr("config.get_voice_config", _boom)
    assert voice.create_realtime_session("x") is None
    print("✅ create_realtime_session never raises")


# ── adapter: enabled path (monkeypatched, no real key, no network) ───────────


def test_session_descriptor_when_enabled(monkeypatch):
    monkeypatch.setattr("config.get_voice_config", _enabled_cfg)
    # Adapter also requires the SDK; skip the enabled assertions if it is absent.
    if not voice.sdk_available():
        pytest.skip("openai SDK not installed")
    assert voice.voice_enabled() is True
    desc = voice.create_realtime_session("be concise")
    assert desc is not None
    assert desc["model"] == "gpt-4o-realtime-preview"
    assert desc["voice"] == "alloy"
    assert desc["modalities"] == ["audio", "text"]
    assert desc["instructions"] == "be concise"
    # The descriptor must NOT carry the secret.
    assert "api_key" not in desc
    assert _REAL_KEY not in str(desc.values())
    print("✅ enabled descriptor ok, no key leaked")


# ── api: REST surface ────────────────────────────────────────────────────────


pytestmark_api = pytest.mark.skipif(
    TestClient is None, reason="fastapi TestClient (httpx) not installed"
)


def _make_app() -> "FastAPI":
    from api.routes import voice as voice_routes

    app = FastAPI()
    app.include_router(voice_routes.router, prefix="/api/v1/voice")
    return app


@pytestmark_api
def test_api_status_ok(monkeypatch):
    monkeypatch.setattr(
        "config.get_voice_config",
        lambda: VoiceConfig(api_key="", flag_enabled=False),
    )
    client = TestClient(_make_app())
    resp = client.get("/api/v1/voice/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["enabled"] is False
    assert "api_key" not in body
    print("✅ GET /status -> 200, disabled")


@pytestmark_api
def test_api_session_disabled_503(monkeypatch):
    monkeypatch.setattr(
        "config.get_voice_config",
        lambda: VoiceConfig(api_key="", flag_enabled=False),
    )
    client = TestClient(_make_app())
    resp = client.post("/api/v1/voice/session", json={"instructions": "hi"})
    assert resp.status_code == 503
    print("✅ POST /session disabled -> 503")


@pytestmark_api
def test_api_session_enabled_returns_descriptor(monkeypatch):
    monkeypatch.setattr("config.get_voice_config", _enabled_cfg)
    if not voice.sdk_available():
        pytest.skip("openai SDK not installed")
    client = TestClient(_make_app())
    resp = client.post("/api/v1/voice/session", json={"instructions": "be brief"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["model"] == "gpt-4o-realtime-preview"
    assert body["instructions"] == "be brief"
    assert "api_key" not in body
    assert _REAL_KEY not in str(body.values())
    print("✅ POST /session enabled -> descriptor, no key")
