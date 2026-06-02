"""
Tests for the credential-aware model router (PR3): routing/profiles.py,
routing/router.py, and the api/routes/models.py HTTP surface.

All tests run with NO LLM credentials and NO network. Provider availability and
the client factory are injected so resolution and caching are exercised
deterministically; the API tests exercise the real ``get_router()`` wiring,
which degrades to ``resolvable: false`` (200) when no provider has credentials.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import MissingModelCredentialsError
from routing import (
    ModelCatalogError,
    ModelRouter,
    build_catalog,
    get_router,
    load_catalog,
    reset_router_for_tests,
)

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
except Exception:  # pragma: no cover - httpx missing
    FastAPI = None  # type: ignore[assignment]
    TestClient = None  # type: ignore[assignment]


# ── test doubles ─────────────────────────────────────────────────────────────


class _FakeModelConfig:
    """Minimal stand-in for ModelConfig with injectable credential flags."""

    def __init__(
        self,
        *,
        azure: bool = False,
        openai: bool = False,
        azure_endpoint: str = "https://AZURE-SECRET.example.com",
        azure_api_version: str = "2024-01-01",
        azure_api_key: str = "AZURE-KEY-SECRET",
        openai_api_key: str = "sk-OPENAI-SECRET",
    ) -> None:
        self.has_azure_credentials = azure
        self.has_openai_credentials = openai
        self.azure_endpoint = azure_endpoint
        self.azure_api_version = azure_api_version
        self.azure_api_key = azure_api_key
        self.openai_api_key = openai_api_key


def _avail(*providers: str):
    allowed = set(providers)
    return lambda provider: provider in allowed


def _minimal_catalog_dict() -> dict:
    return {
        "default_profile": "balanced",
        "profiles": {
            "balanced": {"provider": "azure_openai", "model": "gpt-x", "tier": "bal"},
            "openai_balanced": {"provider": "openai", "model": "gpt-4o"},
            "deep": {
                "provider": "anthropic",
                "model": "claude-opus",
                "fallback": ["balanced", "openai_balanced"],
            },
        },
    }


# ── catalog: happy path ──────────────────────────────────────────────────────


def test_real_catalog_loads_and_is_consistent():
    catalog = load_catalog()
    assert catalog.default_profile == "balanced"
    assert catalog.get(catalog.default_profile) is not None
    assert len(catalog.profiles) >= 3
    # At least one buildable profile must exist.
    assert any(p.buildable for p in catalog.profiles.values())
    print("✅ real config/models.yaml loads and is internally consistent")


def test_resolution_order_is_cycle_safe():
    data = _minimal_catalog_dict()
    # Introduce a cycle: balanced -> deep -> balanced.
    data["profiles"]["balanced"]["fallback"] = ["deep"]
    catalog = build_catalog(data)
    order = catalog.resolution_order("deep")
    # No duplicates, terminates, includes both nodes once.
    assert order.count("deep") == 1
    assert order.count("balanced") == 1
    print("✅ resolution_order is cycle-safe and de-duplicated")


# ── catalog: validation errors ───────────────────────────────────────────────


@pytest.mark.parametrize(
    "mutate, needle",
    [
        (lambda d: d["profiles"]["balanced"].pop("provider"), "missing 'provider'"),
        (lambda d: d["profiles"]["balanced"].pop("model"), "missing 'model'"),
        (
            lambda d: d["profiles"]["balanced"].update(provider="cohere"),
            "unknown provider",
        ),
        (
            lambda d: d["profiles"]["deep"].update(fallback=["nope"]),
            "undefined fallback",
        ),
        (lambda d: d.pop("default_profile"), "must define 'default_profile'"),
        (
            lambda d: d.update(default_profile="ghost"),
            "is not a defined profile",
        ),
    ],
)
def test_build_catalog_rejects_malformed(mutate, needle):
    data = _minimal_catalog_dict()
    mutate(data)
    with pytest.raises(ModelCatalogError) as exc:
        build_catalog(data)
    assert needle in str(exc.value)


def test_build_catalog_requires_a_buildable_profile():
    data = {
        "default_profile": "only",
        "profiles": {"only": {"provider": "anthropic", "model": "claude"}},
    }
    with pytest.raises(ModelCatalogError) as exc:
        build_catalog(data)
    assert "no buildable profile" in str(exc.value)


def test_build_catalog_requires_buildable_fallback_path():
    data = {
        "default_profile": "anchor",
        "profiles": {
            "anchor": {"provider": "openai", "model": "gpt-4o"},
            "stranded": {"provider": "anthropic", "model": "claude"},
        },
    }
    # 'stranded' has no fallback to a buildable provider -> dead end.
    with pytest.raises(ModelCatalogError) as exc:
        build_catalog(data)
    assert "no fallback path to a buildable provider" in str(exc.value)


def test_policy_typos_warn_but_do_not_fail():
    data = _minimal_catalog_dict()
    data["policy"] = {"good_agent": "balanced", "typo_agent": "does-not-exist"}
    catalog = build_catalog(data)
    assert catalog.policy == {"good_agent": "balanced"}
    assert any("typo_agent" in w for w in catalog.warnings)
    print("✅ policy entries with unknown targets are dropped with a warning")


# ── router: resolution matrix (injected availability, no creds) ───────────────


def test_resolve_direct_provider_no_substitution():
    router = ModelRouter(
        load_catalog(),
        model_config=_FakeModelConfig(azure=True),
        availability=_avail("azure_openai"),
    )
    resolved = router.resolve("balanced")
    assert resolved.provider == "azure_openai"
    assert resolved.substituted is False


def test_resolve_falls_back_past_non_buildable_to_openai():
    router = ModelRouter(
        load_catalog(),
        model_config=_FakeModelConfig(openai=True),
        availability=_avail("openai"),
    )
    resolved = router.resolve("deep")  # anthropic -> fallback chain
    assert resolved.provider == "openai"
    assert resolved.substituted is True


def test_resolve_unknown_profile_anchors_on_default():
    router = ModelRouter(
        load_catalog(),
        model_config=_FakeModelConfig(azure=True),
        availability=_avail("azure_openai"),
    )
    resolved = router.resolve("does-not-exist")
    # Anchors on default_profile, flagged as substituted.
    assert resolved.substituted is True
    assert resolved.provider == "azure_openai"


def test_resolve_raises_when_no_provider_has_credentials():
    router = ModelRouter(
        load_catalog(),
        model_config=_FakeModelConfig(),  # no creds
        availability=_avail(),  # nothing available
    )
    with pytest.raises(MissingModelCredentialsError):
        router.resolve("balanced")


# ── router: client cache (secret-free key, build-once) ────────────────────────


def test_build_client_is_cached_and_key_is_secret_free():
    calls = {"n": 0}
    seen_kwargs = []

    def factory(**kwargs):
        calls["n"] += 1
        seen_kwargs.append(kwargs)
        return object()

    router = ModelRouter(
        load_catalog(),
        model_config=_FakeModelConfig(azure=True),
        availability=_avail("azure_openai"),
        client_factory=factory,
    )
    c1 = router.build_client("balanced")
    c2 = router.build_client("balanced")
    assert c1 is c2
    assert calls["n"] == 1  # built once, then cached

    # Cache key is minimal — (provider, model) only. Endpoint/api_version are
    # invariant for a router instance, so they add no disambiguation and must
    # never be embedded in the key (which lives in process memory).
    azure_key = router._cache_key("azure_openai", "m")
    openai_key = router._cache_key("openai", "m")
    assert azure_key == ("azure_openai", "m")
    assert openai_key == ("openai", "m")
    # The cache key must never contain the endpoint or the API key.
    assert "AZURE-SECRET.example.com" not in azure_key
    assert "AZURE-KEY-SECRET" not in azure_key
    print("✅ build_client caches once; cache key is minimal and secret-free")


def test_describe_is_secret_free():
    router = ModelRouter(
        load_catalog(),
        model_config=_FakeModelConfig(azure=True, openai=True),
        availability=_avail("azure_openai", "openai"),
    )
    payload = json.dumps(router.describe())
    assert "AZURE-SECRET.example.com" not in payload
    assert "AZURE-KEY-SECRET" not in payload
    assert "sk-OPENAI-SECRET" not in payload
    # But it should still report credential booleans.
    assert router.describe()["credentials"] == {"azure": True, "openai": True}
    print("✅ describe() exposes credential booleans but no secrets")


# ── singleton lifecycle ───────────────────────────────────────────────────────


def test_get_router_is_singleton_until_reset():
    reset_router_for_tests()
    r1 = get_router()
    r2 = get_router()
    assert r1 is r2
    reset_router_for_tests()
    r3 = get_router()
    assert r3 is not r1
    reset_router_for_tests()
    print("✅ get_router() is a resettable process singleton")


# ── HTTP surface (api/routes/models.py) ───────────────────────────────────────


pytestmark = pytest.mark.skipif(
    TestClient is None, reason="fastapi TestClient (httpx) not installed"
)


def _make_app() -> "FastAPI":
    from api.routes.models import router as models_router

    app = FastAPI()
    app.include_router(models_router, prefix="/api/v1/models")
    return app


def test_models_describe_endpoint_returns_200_no_secrets(monkeypatch):
    # Seed secret-looking, NON-placeholder credentials so the leak check is
    # meaningful: with creds present the endpoint reports `credentials.azure:
    # true`, but none of the seeded secret VALUES — nor any secret-bearing field
    # NAME — may appear anywhere in the serialized response.
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://LEAK-ENDPOINT.example.com")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "AZURE-LEAK-KEY")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-LEAK-OPENAI")
    reset_router_for_tests()
    client = TestClient(_make_app())
    resp = client.get("/api/v1/models")
    assert resp.status_code == 200
    body = resp.json()
    assert "default_profile" in body
    assert "credentials" in body
    serialized = json.dumps(body).lower()
    # No seeded secret VALUE may leak.
    for secret in ("leak-endpoint.example.com", "azure-leak-key", "sk-leak-openai"):
        assert secret not in serialized, f"leaked secret value: {secret}"
    # No secret-bearing field NAME may leak (verified absent from real describe()).
    for field in ("api_key", "endpoint", "authorization", "token", "base_url", "azure_endpoint"):
        assert field not in serialized, f"leaked secret-bearing field: {field}"
    reset_router_for_tests()
    print("✅ GET /models returns 200 and leaks neither secret values nor field names")


def test_models_resolve_unknown_profile_is_404(monkeypatch):
    reset_router_for_tests()
    client = TestClient(_make_app())
    resp = client.get("/api/v1/models/resolve/does-not-exist")
    assert resp.status_code == 404
    reset_router_for_tests()
    print("✅ GET /models/resolve/<unknown> returns 404")


def test_models_resolve_without_creds_is_200_unresolvable(monkeypatch):
    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    reset_router_for_tests()
    client = TestClient(_make_app())
    resp = client.get("/api/v1/models/resolve/balanced")
    assert resp.status_code == 200
    body = resp.json()
    assert body["resolvable"] is False
    assert "reason" in body
    reset_router_for_tests()
    print("✅ GET /models/resolve/balanced degrades to 200 resolvable:false")


# ── deep(anthropic) policy path: never build Anthropic, fall back cleanly ──────


def test_deep_anthropic_profile_never_builds_and_falls_back():
    """A ``deep`` (anthropic) profile — the policy target for the heavyweight
    agents — must NEVER instantiate an Anthropic client. With no credentials it
    raises a clean MissingModelCredentialsError and never touches the factory;
    with a buildable provider available it resolves past anthropic to the
    fallback and builds exactly that provider's client.

    This exercises the router contract the orchestrator relies on in
    ``_client_for_agent`` (it just delegates to ``build_client``), without
    standing up the whole orchestrator.
    """
    built: list[dict] = []

    def factory(**kwargs):
        built.append(kwargs)
        return object()

    catalog = build_catalog(_minimal_catalog_dict())

    # (a) No credentials anywhere → clean error, factory NEVER called.
    no_cred = ModelRouter(
        catalog,
        model_config=_FakeModelConfig(),  # no flags
        availability=_avail(),            # nothing usable
        client_factory=factory,
    )
    with pytest.raises(MissingModelCredentialsError):
        no_cred.build_client("deep")
    assert built == []  # anthropic (and everything else) skipped before building

    # (b) Only OpenAI available → deep falls back PAST anthropic to openai_balanced.
    openai_only = ModelRouter(
        catalog,
        model_config=_FakeModelConfig(openai=True),
        availability=_avail("openai"),
        client_factory=factory,
    )
    resolved = openai_only.resolve("deep")
    assert resolved.provider == "openai"        # never anthropic
    assert resolved.profile.name == "openai_balanced"
    assert resolved.substituted is True
    client = openai_only.build_client("deep")
    assert client is not None
    assert len(built) == 1                       # exactly one client built
    assert built[0].get("api_key") == "sk-OPENAI-SECRET"   # openai code path
    assert built[0].get("model") != "claude-opus"          # not the anthropic model
    assert "azure_endpoint" not in built[0]                # not the azure code path

    # (c) Even if 'anthropic' is (wrongly) reported available, the
    #     BUILDABLE_PROVIDERS gate keeps it unbuildable → still falls back.
    forced = ModelRouter(
        catalog,
        model_config=_FakeModelConfig(openai=True),
        availability=_avail("anthropic", "openai"),
        client_factory=factory,
    )
    assert forced.resolve("deep").provider == "openai"
    print("✅ deep(anthropic) profile never builds Anthropic; falls back cleanly")


# ── shipped .env.template endpoint must read as a placeholder ──────────────────


def test_shipped_template_endpoint_is_detected_as_placeholder():
    """The ``AZURE_OPENAI_ENDPOINT`` shipped in ``.env.template`` has no angle
    brackets, so a copied-but-unedited template would otherwise read as a real
    endpoint and flip ``has_azure_credentials`` true the moment a real key is
    supplied. Assert the SHIPPED value is recognized as a placeholder, reading
    the live template so this can't silently drift.
    """
    import pathlib

    from config import _is_placeholder

    template = pathlib.Path(__file__).resolve().parents[1] / ".env.template"
    assert template.exists(), f"missing template: {template}"

    endpoint = None
    for line in template.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("AZURE_OPENAI_ENDPOINT="):
            endpoint = stripped.split("=", 1)[1].strip().strip('"').strip("'")
            break

    assert endpoint, "AZURE_OPENAI_ENDPOINT not found in .env.template"
    assert _is_placeholder(endpoint), (
        f"shipped template endpoint {endpoint!r} is not detected as a placeholder"
    )
    print("✅ shipped .env.template endpoint is detected as a placeholder")
