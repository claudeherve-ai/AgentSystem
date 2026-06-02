"""
AgentSystem — Model Router Routes (PR3)

Read-only introspection over the per-agent multi-model router. Lets operators see
which profiles exist, which providers currently have credentials, the agent→profile
policy, and how a given profile resolves *right now* (including graceful fallback
when a declared-but-not-buildable provider — e.g. Anthropic without a key — is the
nominal target).

Endpoints (mounted under ``/api/v1/models``):
    GET ""                 Whole-router status (profiles, policy, credential flags).
    GET /resolve/{profile} How ``profile`` resolves now (or why it can't).

Secret-free by construction: the router's ``describe()`` / ``ResolvedModel`` payloads
never include endpoints or API keys. Sits behind ``AuthMiddleware`` like every other
``/api/v1`` route. A broken catalog degrades to 503 rather than crashing the app.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from config import MissingModelCredentialsError
from routing import ModelCatalogError, get_router

router = APIRouter()


@router.get("")
async def describe_models():
    """Return the whole-router status (profiles, policy, credentials, warnings)."""
    try:
        return get_router().describe()
    except ModelCatalogError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Model catalog is invalid: {exc}",
        ) from exc


@router.get("/resolve/{profile}")
async def resolve_profile(profile: str):
    """Resolve ``profile`` to a concrete buildable model, or explain why it can't.

    * 404 — the profile is not defined in the catalog.
    * 200 with ``resolvable: false`` — defined, but no provider along its fallback
      chain currently has credentials (the same condition that yields a clean 503
      at chat time). Returned as 200 so callers can introspect without error noise.
    * 503 — the catalog itself failed to load.
    """
    try:
        router_obj = get_router()
    except ModelCatalogError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Model catalog is invalid: {exc}",
        ) from exc

    if router_obj.catalog.get(profile) is None:
        raise HTTPException(
            status_code=404,
            detail=f"Profile '{profile}' is not defined.",
        )

    try:
        return router_obj.resolve(profile).to_dict()
    except MissingModelCredentialsError as exc:
        return {
            "requested_profile": profile,
            "resolvable": False,
            "reason": str(exc),
        }
