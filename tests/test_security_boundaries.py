from __future__ import annotations

from pathlib import Path

import pytest

from agentsystem.errors import DependencyUnavailableError, UnauthorizedError
from agentsystem.services.identity import IdentityExtractor
from agentsystem.services.rate_limit import RedisRateLimiter


ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.asyncio
async def test_entra_mode_rejects_forgeable_easy_auth_header(clean_settings, easy_auth):
    settings = clean_settings(
        APP_ENV="production",
        AUTH_MODE="entra_jwt",
        ENTRA_TENANT_ID="tenant",
        ENTRA_AUDIENCE="client",
    )

    with pytest.raises(UnauthorizedError, match="missing bearer token"):
        await IdentityExtractor(settings).extract(
            {"x-ms-client-principal": easy_auth(oid="user", tid="tenant")}
        )


def test_frontend_proxy_replaces_client_identity_with_signed_token():
    config = (ROOT / "frontend" / "nginx.conf.template").read_text(encoding="utf-8")

    assert 'proxy_set_header X-MS-CLIENT-PRINCIPAL "";' in config
    assert 'proxy_set_header X-MS-CLIENT-PRINCIPAL-ID "";' in config
    assert "$http_x_ms_token_aad_id_token" in config
    assert "proxy_ssl_name $proxy_host;" in config


def test_redis_entra_auth_requires_object_id():
    limiter = RedisRateLimiter(
        "rediss://redis.test:10000",
        10,
        60,
        use_entra=True,
        entra_username="",
    )

    with pytest.raises(DependencyUnavailableError, match="REDIS_USERNAME"):
        limiter._get_client()


def test_redis_entra_auth_passes_object_id_to_provider(monkeypatch):
    import redis.asyncio as redis

    captured = {}

    def fake_from_url(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(redis, "from_url", fake_from_url)
    limiter = RedisRateLimiter(
        "rediss://redis.test:10000",
        10,
        60,
        use_entra=True,
        entra_username="managed-identity-object-id",
    )

    limiter._get_client()

    assert captured["credential_provider"]._username == "managed-identity-object-id"
