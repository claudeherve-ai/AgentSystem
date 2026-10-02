from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from agentsystem.context import Principal
from agentsystem.services.rate_limit import InMemoryRateLimiter
from api.middleware.context import (
    IdentityMiddleware,
    PrincipalRateLimitMiddleware,
    SharedRateLimitMiddleware,
)


def _rate_limited_app(monkeypatch) -> TestClient:
    app = FastAPI()

    @app.get("/private")
    async def private(request: Request):
        return {"user": request.state.principal.user_id}

    async def extract(_extractor, headers):
        return Principal(
            tenant_id="tenant-a",
            user_id=headers["authorization"],
            auth_method="test",
        )

    settings = SimpleNamespace(
        rate_limit_enabled=True,
        rate_limit_requests=1,
    )
    limiter = InMemoryRateLimiter(max_requests=1, window_seconds=60)
    monkeypatch.setattr(
        "api.middleware.context.IdentityExtractor.extract", extract
    )
    monkeypatch.setattr("api.middleware.context.get_settings", lambda: settings)
    monkeypatch.setattr(
        "api.middleware.context.get_rate_limiter", lambda: limiter
    )

    app.add_middleware(PrincipalRateLimitMiddleware)
    app.add_middleware(IdentityMiddleware)
    app.add_middleware(SharedRateLimitMiddleware)
    return TestClient(app)


def test_authenticated_users_behind_same_proxy_have_independent_buckets(
    monkeypatch,
):
    client = _rate_limited_app(monkeypatch)

    assert client.get("/private", headers={"Authorization": "user-a"}).status_code == 200
    assert client.get("/private", headers={"Authorization": "user-b"}).status_code == 200
    assert client.get("/private", headers={"Authorization": "user-a"}).status_code == 429


def test_principal_rate_limit_is_scoped_by_tenant_and_user(monkeypatch):
    app = FastAPI()

    @app.get("/private")
    async def private(request: Request):
        return {"user": request.state.principal.user_id}

    async def extract(_extractor, headers):
        tenant_id, user_id = headers["authorization"].split("/")
        return Principal(
            tenant_id=tenant_id,
            user_id=user_id,
            auth_method="test",
        )

    settings = SimpleNamespace(rate_limit_enabled=True, rate_limit_requests=1)
    limiter = InMemoryRateLimiter(max_requests=1, window_seconds=60)
    monkeypatch.setattr(
        "api.middleware.context.IdentityExtractor.extract", extract
    )
    monkeypatch.setattr("api.middleware.context.get_settings", lambda: settings)
    monkeypatch.setattr(
        "api.middleware.context.get_rate_limiter", lambda: limiter
    )

    app.add_middleware(PrincipalRateLimitMiddleware)
    app.add_middleware(IdentityMiddleware)
    client = TestClient(app)

    assert client.get("/private", headers={"Authorization": "t1/user"}).status_code == 200
    assert client.get("/private", headers={"Authorization": "t2/user"}).status_code == 200
    assert client.get("/private", headers={"Authorization": "t1/user"}).status_code == 429
