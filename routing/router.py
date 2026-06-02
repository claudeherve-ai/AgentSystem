"""AgentSystem — Credential-aware model router (PR3).

This is the only layer that touches credentials. It resolves a profile name to a
concrete, *buildable* model (walking the catalog's fallback chain past providers
that are declared-but-not-buildable or simply lack credentials), and lazily
builds + caches the underlying chat-completion client.

Key guarantees
--------------
* **No secrets in caches or status.** The client cache key never includes an API
  key, and every status/describe method returns provider/model/cost metadata
  only — never endpoints or keys.
* **Live credentials.** ``config.ModelConfig`` reads credentials from the
  environment on every access, so a long-lived (cached) router still reflects
  credential changes; only the catalog and built clients are cached.
* **Graceful degradation.** ``resolve`` never builds a client and raises
  :class:`MissingModelCredentialsError` (with chain context) only when no
  profile in the chain is usable. Callers translate that into the same clean 503
  the legacy path already produces.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from agent_framework.openai import OpenAIChatCompletionClient

from config import (
    MissingModelCredentialsError,
    ModelConfig,
    get_model_config,
    get_models_config,
)
from routing.profiles import (
    BUILDABLE_PROVIDERS,
    ModelCatalog,
    ModelProfile,
    load_catalog,
)

# Returns True when a *buildable* provider has usable credentials right now.
ProviderAvailability = Callable[[str], bool]
# Builds the underlying client; injectable so tests never need real creds.
ClientFactory = Callable[..., OpenAIChatCompletionClient]


@dataclass(frozen=True, slots=True)
class ResolvedModel:
    """The concrete model a profile resolved to, plus provenance."""

    requested_profile: str
    profile: ModelProfile
    provider: str
    model: str
    substituted: bool = False
    reason: Optional[str] = None
    tried: tuple[str, ...] = ()

    def as_attributes(self, prefix: str = "model") -> dict[str, Any]:
        """Flatten to telemetry-span attributes (secret-free)."""
        return {
            f"{prefix}.requested_profile": self.requested_profile,
            f"{prefix}.profile": self.profile.name,
            f"{prefix}.provider": self.provider,
            f"{prefix}.name": self.model,
            f"{prefix}.tier": self.profile.tier,
            f"{prefix}.substituted": self.substituted,
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize for API responses (secret-free)."""
        return {
            "requested_profile": self.requested_profile,
            "resolved_profile": self.profile.name,
            "provider": self.provider,
            "model": self.model,
            "tier": self.profile.tier,
            "substituted": self.substituted,
            "reason": self.reason,
            "tried": list(self.tried),
            "resolvable": True,
        }


def _default_availability(model_cfg: ModelConfig) -> ProviderAvailability:
    """Availability backed by live credential checks on ``ModelConfig``."""

    def _available(provider: str) -> bool:
        if provider == "azure_openai":
            return model_cfg.has_azure_credentials
        if provider == "openai":
            return model_cfg.has_openai_credentials
        return False

    return _available


class ModelRouter:
    """Resolves catalog profiles to buildable clients with graceful fallback."""

    def __init__(
        self,
        catalog: ModelCatalog,
        model_config: Optional[ModelConfig] = None,
        availability: Optional[ProviderAvailability] = None,
        client_factory: Optional[ClientFactory] = None,
    ) -> None:
        self._catalog = catalog
        self._model_config = model_config or get_model_config()
        self._availability = availability or _default_availability(self._model_config)
        self._client_factory = client_factory or OpenAIChatCompletionClient
        self._lock = threading.Lock()
        self._client_cache: dict[tuple[str, str], OpenAIChatCompletionClient] = {}

    @property
    def catalog(self) -> ModelCatalog:
        return self._catalog

    # ── resolution (never builds, never touches the network) ──────────────
    def _provider_usable(self, provider: str) -> bool:
        return provider in BUILDABLE_PROVIDERS and self._availability(provider)

    def resolve(self, profile_name: Optional[str] = None) -> ResolvedModel:
        """Resolve a profile to the first usable model along its fallback chain.

        Unknown / missing profile names anchor on ``default_profile`` and are
        marked ``substituted``. Raises :class:`MissingModelCredentialsError` when
        no profile in the chain has a usable, buildable provider.
        """
        requested = profile_name or self._catalog.default_profile
        anchor = requested
        substituted = False
        reason: Optional[str] = None

        if self._catalog.get(anchor) is None:
            anchor = self._catalog.default_profile
            substituted = True
            reason = (
                f"profile '{requested}' is not defined; "
                f"using default '{anchor}'."
            )

        order = self._catalog.resolution_order(anchor)
        for candidate_name in order:
            candidate = self._catalog.profiles[candidate_name]
            if self._provider_usable(candidate.provider):
                if candidate_name != requested:
                    substituted = True
                    if reason is None:
                        reason = (
                            f"profile '{requested}' ({self._catalog.profiles[anchor].provider}) "
                            f"is unavailable; routed to '{candidate_name}'."
                        )
                return ResolvedModel(
                    requested_profile=requested,
                    profile=candidate,
                    provider=candidate.provider,
                    model=candidate.model,
                    substituted=substituted,
                    reason=reason,
                    tried=tuple(order),
                )

        raise MissingModelCredentialsError(
            f"No usable provider for profile '{requested}'. Tried "
            f"{order} but none of azure_openai/openai had credentials. "
            "Set AZURE_OPENAI_ENDPOINT + AZURE_OPENAI_API_KEY, or OPENAI_API_KEY."
        )

    # ── client building (cached; secret-free cache key) ───────────────────
    def _cache_key(self, provider: str, model: str) -> tuple[str, str]:
        # ``(provider, model)`` fully distinguishes clients within a single
        # router instance: ``_model_config`` (and thus the endpoint/api_version)
        # is fixed for the router's lifetime, so those values never vary across
        # resolves and add no disambiguation. Keeping the key minimal also
        # guarantees the endpoint string is never retained inside a cache key.
        return (provider, model)

    def _make_client(self, provider: str, model: str) -> OpenAIChatCompletionClient:
        if provider == "azure_openai":
            return self._client_factory(
                model=model,
                azure_endpoint=self._model_config.azure_endpoint,
                api_key=self._model_config.azure_api_key,
                api_version=self._model_config.azure_api_version,
            )
        return self._client_factory(
            model=model,
            api_key=self._model_config.openai_api_key,
        )

    def build_client(
        self, profile_name: Optional[str] = None
    ) -> OpenAIChatCompletionClient:
        """Resolve ``profile_name`` then return a cached/built client for it."""
        resolved = self.resolve(profile_name)
        key = self._cache_key(resolved.provider, resolved.model)
        with self._lock:
            client = self._client_cache.get(key)
            if client is None:
                client = self._make_client(resolved.provider, resolved.model)
                self._client_cache[key] = client
            return client

    # ── introspection (secret-free) ───────────────────────────────────────
    def estimate_cost(
        self, profile_name: str, prompt_tokens: int, completion_tokens: int
    ) -> dict[str, Any]:
        """Estimate request cost (USD) from illustrative catalog pricing."""
        profile = self._catalog.get(profile_name)
        if profile is None:
            return {"profile": profile_name, "known": False, "estimated_usd": 0.0}
        usd = (
            (prompt_tokens / 1000.0) * profile.cost_per_1k_input
            + (completion_tokens / 1000.0) * profile.cost_per_1k_output
        )
        return {
            "profile": profile_name,
            "known": True,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "estimated_usd": round(usd, 6),
        }

    def profile_status(self, name: str) -> dict[str, Any]:
        """Per-profile status (no endpoint, no key)."""
        profile = self._catalog.get(name)
        if profile is None:
            return {"name": name, "defined": False}
        available = self._provider_usable(profile.provider)
        resolves_to: Optional[str] = None
        resolvable = False
        try:
            resolved = self.resolve(name)
            resolves_to = resolved.profile.name
            resolvable = True
        except MissingModelCredentialsError:
            resolvable = False
        return {
            "name": profile.name,
            "defined": True,
            "provider": profile.provider,
            "model": profile.model,
            "tier": profile.tier,
            "cost_per_1k_input": profile.cost_per_1k_input,
            "cost_per_1k_output": profile.cost_per_1k_output,
            "buildable": profile.buildable,
            "available": available,
            "fallback": list(profile.fallback),
            "resolvable": resolvable,
            "resolves_to": resolves_to,
        }

    def describe(self) -> dict[str, Any]:
        """Whole-router status for the /models API (secret-free)."""
        return {
            "default_profile": self._catalog.default_profile,
            "buildable_providers": sorted(BUILDABLE_PROVIDERS),
            "credentials": {
                "azure": self._model_config.has_azure_credentials,
                "openai": self._model_config.has_openai_credentials,
            },
            "policy": dict(self._catalog.policy),
            "warnings": list(self._catalog.warnings),
            "profiles": {
                name: self.profile_status(name)
                for name in self._catalog.profiles
            },
        }


# ── module singleton ──────────────────────────────────────────────────────
_router_lock = threading.Lock()
_router_singleton: Optional[ModelRouter] = None


def get_router() -> ModelRouter:
    """Return the process-wide router, building it once from the catalog.

    Cached for reuse, but ``ModelConfig`` is read live, so credential changes
    are still reflected. Raises :class:`ModelCatalogError` if the catalog itself
    is invalid — callers (orchestrator/API) handle that by degrading gracefully.
    """
    global _router_singleton
    if _router_singleton is None:
        with _router_lock:
            if _router_singleton is None:
                models_cfg = get_models_config()
                catalog = load_catalog(models_cfg.config_path or None)
                _router_singleton = ModelRouter(catalog)
    return _router_singleton


def reset_router_for_tests() -> None:
    """Drop the cached router (test isolation helper)."""
    global _router_singleton
    with _router_lock:
        _router_singleton = None
