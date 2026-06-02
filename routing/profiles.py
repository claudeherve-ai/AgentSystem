"""AgentSystem — Model catalog: declarative profiles + validation (PR3).

This module is intentionally pure: it parses and validates the model catalog
(``config/models.yaml``) into immutable dataclasses. It performs NO network
calls, builds NO clients, and touches NO credentials. All credential-aware
behavior lives in :mod:`routing.router`.

Design notes
------------
* ``anthropic`` is a *known* provider you may declare, but it is not
  *buildable* yet (no client wired in). The catalog therefore enforces that
  every profile's fallback chain eventually reaches a buildable provider, so a
  profile pinned to a non-buildable provider always has a usable landing spot.
* Validation is strict and fails loudly with :class:`ModelCatalogError` so a
  malformed catalog is caught at load time, not at request time. The router, in
  turn, degrades gracefully if catalog loading fails (it falls back to the
  legacy single-client path), so a broken catalog never takes the app down.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

# Providers the router can actually instantiate a client for today.
BUILDABLE_PROVIDERS = frozenset({"azure_openai", "openai"})
# Providers that may be *declared* in the catalog (buildable + aspirational).
KNOWN_PROVIDERS = BUILDABLE_PROVIDERS | {"anthropic"}

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class ModelCatalogError(ValueError):
    """Raised when ``models.yaml`` is missing, malformed, or self-inconsistent."""


@dataclass(frozen=True, slots=True)
class ModelProfile:
    """One named model profile from the catalog."""

    name: str
    provider: str
    model: str
    tier: str = ""
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0
    fallback: tuple[str, ...] = ()

    @property
    def buildable(self) -> bool:
        """True when this profile's provider can be instantiated today."""
        return self.provider in BUILDABLE_PROVIDERS


@dataclass(frozen=True, slots=True)
class ModelCatalog:
    """Validated, immutable view over the model catalog."""

    profiles: dict[str, ModelProfile]
    default_profile: str
    policy: dict[str, str] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()

    def get(self, name: Optional[str]) -> Optional[ModelProfile]:
        """Return the profile for ``name`` (None if unknown / falsy)."""
        if not name:
            return None
        return self.profiles.get(name)

    def resolution_order(self, name: str) -> list[str]:
        """Cycle-safe preorder DFS over a profile's fallback chain.

        Returns the profile names to try, in order, starting with ``name``
        itself, then its fallbacks (depth-first), de-duplicated. Unknown names
        are skipped. The traversal never loops even if profiles reference each
        other cyclically.
        """
        order: list[str] = []
        seen: set[str] = set()

        def _walk(profile_name: str) -> None:
            if profile_name in seen:
                return
            profile = self.profiles.get(profile_name)
            if profile is None:
                return
            seen.add(profile_name)
            order.append(profile_name)
            for nxt in profile.fallback:
                _walk(nxt)

        _walk(name)
        return order


def _require_mapping(data: Any, what: str) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ModelCatalogError(f"{what} must be a mapping, got {type(data).__name__}.")
    return data


def build_catalog(data: Any) -> ModelCatalog:
    """Validate raw catalog ``data`` and build an immutable :class:`ModelCatalog`.

    Raises :class:`ModelCatalogError` on any structural or semantic problem so
    catalog issues are surfaced once, at load time.
    """
    root = _require_mapping(data, "models.yaml")

    raw_profiles = root.get("profiles")
    if not isinstance(raw_profiles, dict) or not raw_profiles:
        raise ModelCatalogError("models.yaml must define a non-empty 'profiles' mapping.")

    profiles: dict[str, ModelProfile] = {}
    for name, spec in raw_profiles.items():
        spec_map = _require_mapping(spec, f"profile '{name}'")
        provider = spec_map.get("provider")
        model = spec_map.get("model")
        if not provider:
            raise ModelCatalogError(f"profile '{name}' is missing 'provider'.")
        if not model:
            raise ModelCatalogError(f"profile '{name}' is missing 'model'.")
        if provider not in KNOWN_PROVIDERS:
            raise ModelCatalogError(
                f"profile '{name}' has unknown provider '{provider}'. "
                f"Known providers: {sorted(KNOWN_PROVIDERS)}."
            )
        raw_fallback = spec_map.get("fallback", [])
        if not isinstance(raw_fallback, list):
            raise ModelCatalogError(f"profile '{name}' fallback must be a list.")
        fallback = tuple(str(f) for f in raw_fallback)
        profiles[name] = ModelProfile(
            name=name,
            provider=str(provider),
            model=str(model),
            tier=str(spec_map.get("tier", "")),
            cost_per_1k_input=float(spec_map.get("cost_per_1k_input", 0.0) or 0.0),
            cost_per_1k_output=float(spec_map.get("cost_per_1k_output", 0.0) or 0.0),
            fallback=fallback,
        )

    # Every fallback reference must point at a defined profile.
    for profile in profiles.values():
        for ref in profile.fallback:
            if ref not in profiles:
                raise ModelCatalogError(
                    f"profile '{profile.name}' references undefined fallback '{ref}'."
                )

    default_profile = root.get("default_profile")
    if not default_profile:
        raise ModelCatalogError("models.yaml must define 'default_profile'.")
    if default_profile not in profiles:
        raise ModelCatalogError(
            f"default_profile '{default_profile}' is not a defined profile."
        )

    # There must be at least one profile we can actually build.
    if not any(p.buildable for p in profiles.values()):
        raise ModelCatalogError(
            "models.yaml defines no buildable profile "
            f"(need a provider in {sorted(BUILDABLE_PROVIDERS)})."
        )

    # Every profile must have a fallback path that reaches a buildable provider,
    # so a profile pinned to a non-buildable provider can never be a dead end.
    catalog_stub = ModelCatalog(profiles=profiles, default_profile=default_profile)
    for profile in profiles.values():
        order = catalog_stub.resolution_order(profile.name)
        if not any(profiles[n].buildable for n in order):
            raise ModelCatalogError(
                f"profile '{profile.name}' has no fallback path to a buildable "
                "provider; add a buildable profile to its 'fallback' chain."
            )

    # Policy: keep only entries whose target is a defined profile; warn on the
    # rest instead of failing (a typo'd policy entry shouldn't break the app).
    warnings: list[str] = []
    policy: dict[str, str] = {}
    raw_policy = root.get("policy", {})
    if raw_policy:
        raw_policy_map = _require_mapping(raw_policy, "policy")
        for agent_name, target in raw_policy_map.items():
            target_str = str(target)
            if target_str not in profiles:
                warnings.append(
                    f"policy entry '{agent_name}' -> '{target_str}' ignored "
                    "(no such profile)."
                )
                continue
            policy[str(agent_name)] = target_str

    return ModelCatalog(
        profiles=profiles,
        default_profile=str(default_profile),
        policy=policy,
        warnings=tuple(warnings),
    )


def load_catalog(path: Optional[Path | str] = None) -> ModelCatalog:
    """Load and validate the catalog from ``path`` (defaults to config/models.yaml)."""
    catalog_path = Path(path) if path else PROJECT_ROOT / "config" / "models.yaml"
    if not catalog_path.exists():
        raise ModelCatalogError(f"models.yaml not found at {catalog_path}.")
    try:
        with open(catalog_path, "r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except yaml.YAMLError as exc:
        raise ModelCatalogError(f"models.yaml is not valid YAML: {exc}") from exc
    return build_catalog(data)
