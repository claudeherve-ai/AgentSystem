"""Unit tests for RunContext, the error envelope, settings, and sandbox resolution."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agentsystem.context import Principal, RunContext, new_id
from agentsystem.errors import (
    AgentSystemError,
    ConflictError,
    NotFoundError,
    ProviderError,
    UnauthorizedError,
    error_envelope,
    sanitize_exception,
)
from agentsystem.sandbox import (
    ENGINE_DOCKER,
    ENGINE_DYNAMIC_SESSIONS,
    ENGINE_OFF,
    ENGINE_REFUSE,
    ENGINE_SUBPROCESS,
    resolve_sandbox_engine,
)


# ── RunContext ──────────────────────────────────────────────────────────────
def test_run_context_is_immutable():
    ctx = RunContext.for_local(session_id="s", run_id="r", request_id="q")
    with pytest.raises(Exception):
        ctx.tenant_id = "other"  # frozen dataclass


@pytest.mark.parametrize("prefix", ["run", "sess", "req", "artifact"])
def test_generated_ids_fit_database_contract(prefix):
    assert len(new_id(prefix)) <= 32


def test_run_context_with_run_returns_new_instance():
    ctx = RunContext.for_local(run_id="r1")
    ctx2 = ctx.with_run("r2")
    assert ctx.run_id == "r1"
    assert ctx2.run_id == "r2"
    assert ctx2.tenant_id == ctx.tenant_id


def test_run_context_from_principal_carries_scope():
    p = Principal(tenant_id="T", user_id="U", roles=("owner",), auth_method="entra_jwt")
    ctx = RunContext.from_principal(
        p, workspace_id="W", project_id="P", session_id="S"
    )
    assert (ctx.tenant_id, ctx.user_id, ctx.workspace_id) == ("T", "U", "W")
    assert ctx.auth_method == "entra_jwt"
    assert "owner" in ctx.roles


def test_log_fields_cover_all_correlation_ids():
    ctx = RunContext.for_local()
    fields = ctx.as_log_fields()
    for key in ("tenant_id", "user_id", "workspace_id", "project_id",
                "session_id", "run_id", "request_id"):
        assert key in fields


# ── Error envelope / sanitization ───────────────────────────────────────────
def test_error_envelope_maps_known_errors():
    env = error_envelope(NotFoundError("x"), "req_1")
    assert env.code == "not_found"
    assert env.status_code == 404
    assert env.request_id == "req_1"
    body = env.to_dict()
    assert body["error"]["code"] == "not_found"
    assert body["error"]["request_id"] == "req_1"


def test_error_envelope_hides_unknown_exception_text():
    secret = "SECRET-CONNECTION-STRING=abc123"
    env = error_envelope(ValueError(secret), "req_2")
    assert env.code == "internal_error"
    assert env.status_code == 500
    assert secret not in str(env.to_dict())


def test_sanitize_exception_drops_provider_text():
    raw = RuntimeError("Azure OpenAI 401: key sk-SECRET")
    wrapped = sanitize_exception(raw)
    assert isinstance(wrapped, ProviderError)
    assert "sk-SECRET" not in wrapped.safe_message()
    assert wrapped.status_code == 503


def test_status_codes_for_domain_errors():
    assert ConflictError().status_code == 409
    assert UnauthorizedError().status_code == 401
    assert AgentSystemError().status_code == 500


# ── Sandbox engine resolution (no-subprocess-in-container regression) ────────
@pytest.mark.parametrize("is_production", [True, False])
def test_auto_never_selects_subprocess_in_container(is_production):
    engine = resolve_sandbox_engine(
        "auto",
        in_container=True,
        is_production=is_production,
        docker_available=False,
        dynamic_sessions_configured=False,
    )
    assert engine == ENGINE_REFUSE
    assert engine != ENGINE_SUBPROCESS


def test_auto_prefers_dynamic_sessions_when_configured():
    engine = resolve_sandbox_engine(
        "auto",
        in_container=True,
        is_production=True,
        docker_available=True,
        dynamic_sessions_configured=True,
    )
    assert engine == ENGINE_DYNAMIC_SESSIONS


def test_auto_uses_docker_when_available_and_no_dynamic_sessions():
    engine = resolve_sandbox_engine(
        "auto",
        in_container=False,
        is_production=False,
        docker_available=True,
        dynamic_sessions_configured=False,
    )
    assert engine == ENGINE_DOCKER


def test_explicit_subprocess_refused_in_container():
    engine = resolve_sandbox_engine(
        "subprocess",
        in_container=True,
        is_production=False,
        docker_available=False,
        dynamic_sessions_configured=False,
    )
    assert engine == ENGINE_REFUSE


def test_explicit_subprocess_allowed_locally():
    engine = resolve_sandbox_engine(
        "subprocess",
        in_container=False,
        is_production=False,
        docker_available=False,
        dynamic_sessions_configured=False,
    )
    assert engine == ENGINE_SUBPROCESS


def test_dynamic_sessions_mode_fails_closed_when_unconfigured():
    engine = resolve_sandbox_engine(
        "dynamic_sessions",
        in_container=False,
        is_production=False,
        docker_available=True,
        dynamic_sessions_configured=False,
    )
    assert engine == ENGINE_REFUSE


def test_off_mode_refuses():
    engine = resolve_sandbox_engine(
        "off",
        in_container=False,
        is_production=False,
        docker_available=True,
        dynamic_sessions_configured=True,
    )
    assert engine == ENGINE_OFF


def test_production_configuration_fails_closed(clean_settings):
    settings = clean_settings(APP_ENV="production")
    assert settings.database_config_ready is False
    assert settings.redis_config_ready is False
    assert settings.durable_config_ready is False
    assert settings.artifact_config_ready is False
    assert settings.auth_config_ready is False
    assert settings.sandbox_config_ready is False


# ── Code interpreter fail-closed integration ────────────────────────────────
def test_code_interpreter_refuses_in_container_without_sandbox(monkeypatch):
    """auto + container + no docker/dynamic-sessions must NOT run a subprocess."""
    import asyncio

    monkeypatch.setenv("CODE_SANDBOX_MODE", "auto")
    monkeypatch.setenv("AGENTSYSTEM_IN_CONTAINER", "true")
    from agentsystem.settings import reset_settings_cache

    reset_settings_cache()
    # Force docker + dynamic sessions unavailable.
    from tools import docker_sandbox
    monkeypatch.setattr(docker_sandbox, "docker_available", lambda: False)

    from tools.code_interpreter import run_python

    out = asyncio.run(run_python("print('should not run')"))
    reset_settings_cache()
    assert "refused" in out.lower()
    assert "should not run" not in out
