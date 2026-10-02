"""Identity extraction for Azure Container Apps.

Produces an authenticated :class:`~agentsystem.context.Principal` from an
incoming request using one of four explicit modes (``settings.auth_mode``):

* ``easy_auth`` — trust the ``X-MS-CLIENT-PRINCIPAL`` header injected by the
  Container Apps / App Service Easy Auth sidecar. The sidecar has ALREADY
  validated the token, so we parse (never re-verify) the header — but ONLY when
  Easy Auth is explicitly enabled, so a client cannot spoof the header against a
  service without the sidecar in front.
* ``entra_jwt`` — verify a bearer JWT's signature against cached Entra OpenID
  signing keys, plus audience and issuer. No unsigned/unverified decoding is
  ever used for authentication.
* ``api_key`` — a static service/local key. Compatibility mode only.
* ``disabled`` — local development. In production this fails closed.

Every failure raises :class:`UnauthorizedError`. In production a missing or
invalid identity always fails closed.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import json
import logging
import secrets
import time
from typing import Any, Optional

from agentsystem.context import (
    LOCAL_TENANT_ID,
    LOCAL_USER_ID,
    Principal,
)
from agentsystem.errors import UnauthorizedError
from agentsystem.settings import Settings, get_settings

logger = logging.getLogger("agentsystem.identity")


# ── Easy Auth header parsing ────────────────────────────────────────────────
def _parse_easy_auth_header(raw: str) -> dict[str, Any]:
    """Decode the base64 JSON ``X-MS-CLIENT-PRINCIPAL`` payload."""
    try:
        decoded = base64.b64decode(raw)
        return json.loads(decoded.decode("utf-8"))
    except (ValueError, binascii.Error, json.JSONDecodeError) as exc:
        raise UnauthorizedError("malformed client principal") from exc


def _claims_from_easy_auth(payload: dict[str, Any]) -> dict[str, str]:
    """Flatten the Easy Auth ``claims`` array into a dict."""
    claims: dict[str, str] = {}
    for claim in payload.get("claims", []) or []:
        typ = claim.get("typ")
        val = claim.get("val")
        if typ and val is not None and typ not in claims:
            claims[typ] = val
    return claims


# Claim URIs Entra emits for oid / tid / roles / name.
_OID_KEYS = (
    "http://schemas.microsoft.com/identity/claims/objectidentifier",
    "oid",
    "sub",
)
_TID_KEYS = (
    "http://schemas.microsoft.com/identity/claims/tenantid",
    "tid",
)
_NAME_KEYS = (
    "name",
    "preferred_username",
    "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name",
)
_ROLE_KEYS = (
    "roles",
    "http://schemas.microsoft.com/ws/2008/06/identity/claims/role",
)


def _first(claims: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = claims.get(key)
        if value:
            return str(value)
    return ""


def _roles_from_claims(claims: dict[str, Any], payload_roles: Any = None) -> tuple[str, ...]:
    roles: list[str] = []
    if isinstance(payload_roles, (list, tuple)):
        roles.extend(str(r) for r in payload_roles)
    for key in _ROLE_KEYS:
        value = claims.get(key)
        if isinstance(value, (list, tuple)):
            roles.extend(str(r) for r in value)
        elif value:
            roles.append(str(value))
    # Dedupe, preserve order.
    seen: set[str] = set()
    ordered: list[str] = []
    for role in roles:
        if role not in seen:
            seen.add(role)
            ordered.append(role)
    return tuple(ordered)


# ── Cached JWKS / JWT verification ──────────────────────────────────────────
class _JWKSCache:
    """Cache for Entra signing keys keyed by JWKS URI."""

    def __init__(self, ttl_seconds: int = 3600) -> None:
        self._ttl = ttl_seconds
        self._clients: dict[str, Any] = {}
        self._fetched_at: dict[str, float] = {}

    def get_client(self, jwks_uri: str):
        import jwt  # PyJWT

        now = time.time()
        client = self._clients.get(jwks_uri)
        if client is None or (now - self._fetched_at.get(jwks_uri, 0)) > self._ttl:
            client = jwt.PyJWKClient(jwks_uri, cache_keys=True)
            self._clients[jwks_uri] = client
            self._fetched_at[jwks_uri] = now
        return client


_jwks_cache = _JWKSCache()


class IdentityExtractor:
    """Extract and validate the caller identity from request headers."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()

    async def extract(self, headers: "HeaderLike") -> Principal:
        mode = self.settings.auth_mode
        if mode == "easy_auth":
            return self._from_easy_auth(headers)
        if mode == "entra_jwt":
            return await self._from_entra_jwt(headers)
        if mode == "api_key":
            return self._from_api_key(headers)
        # mode == "disabled"
        if self.settings.is_production:
            # Never run unauthenticated in production.
            raise UnauthorizedError("authentication is required")
        return Principal(
            tenant_id=LOCAL_TENANT_ID,
            user_id=LOCAL_USER_ID,
            roles=("owner",),
            display_name="local",
            auth_method="local",
        )

    # ── Easy Auth ───────────────────────────────────────────────────────────
    def _from_easy_auth(self, headers: "HeaderLike") -> Principal:
        if not self.settings.easy_auth_enabled:
            # Refuse to trust a spoofable header unless Easy Auth is enabled.
            raise UnauthorizedError("Easy Auth is not enabled")
        raw = headers.get("x-ms-client-principal")
        if not raw:
            raise UnauthorizedError("missing client principal")
        payload = _parse_easy_auth_header(raw)
        claims = _claims_from_easy_auth(payload)
        oid = _first(claims, _OID_KEYS) or headers.get("x-ms-client-principal-id", "")
        tid = _first(claims, _TID_KEYS)
        if not oid or not tid:
            raise UnauthorizedError("client principal is missing oid/tid")
        return Principal(
            tenant_id=tid,
            user_id=oid,
            roles=_roles_from_claims(claims),
            display_name=_first(claims, _NAME_KEYS)
            or headers.get("x-ms-client-principal-name", ""),
            auth_method="easy_auth",
            claims=claims,
        )

    # ── Entra JWT ───────────────────────────────────────────────────────────
    def _bearer(self, headers: "HeaderLike") -> str:
        auth = headers.get("authorization", "")
        if not auth.lower().startswith("bearer "):
            raise UnauthorizedError("missing bearer token")
        return auth[7:].strip()

    async def _from_entra_jwt(self, headers: "HeaderLike") -> Principal:
        if not (self.settings.entra_tenant_id and self.settings.entra_audience):
            raise UnauthorizedError("Entra JWT validation is not configured")
        token = self._bearer(headers)
        claims = await asyncio.to_thread(self._verify_jwt, token)
        oid = _first(claims, _OID_KEYS)
        tid = _first(claims, _TID_KEYS)
        if not oid or not tid:
            raise UnauthorizedError("token missing oid/tid")
        return Principal(
            tenant_id=tid,
            user_id=oid,
            roles=_roles_from_claims(claims, claims.get("roles")),
            display_name=_first(claims, _NAME_KEYS),
            auth_method="entra_jwt",
            claims={k: v for k, v in claims.items() if k not in ("exp", "nbf", "iat")},
        )

    def _verify_jwt(self, token: str) -> dict[str, Any]:
        """Verify signature, audience, and issuer against cached JWKS keys."""
        import jwt

        authority = self.settings.entra_authority.rstrip("/")
        jwks_uri = f"{authority}/discovery/v2.0/keys"
        valid_issuers = {
            f"{authority}/v2.0",
            f"https://sts.windows.net/{self.settings.entra_tenant_id}/",
        }
        try:
            client = _jwks_cache.get_client(jwks_uri)
            signing_key = client.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=self.settings.entra_audience,
                options={"require": ["exp", "iat"]},
            )
        except Exception as exc:  # noqa: BLE001 - any failure is a 401
            logger.info("JWT validation failed: %s", type(exc).__name__)
            raise UnauthorizedError("token validation failed") from exc
        issuer = str(claims.get("iss", ""))
        if issuer not in valid_issuers:
            raise UnauthorizedError("token issuer is not trusted")
        return claims

    # ── Static API key ──────────────────────────────────────────────────────
    def _from_api_key(self, headers: "HeaderLike") -> Principal:
        expected = self.settings.api_key
        if not expected:
            raise UnauthorizedError("API key auth is misconfigured")
        presented = headers.get("x-api-key", "") or self._maybe_bearer(headers)
        if not presented or not secrets.compare_digest(presented, expected):
            raise UnauthorizedError("invalid API key")
        # A static key authenticates a SERVICE identity in a dedicated tenant.
        return Principal(
            tenant_id="service",
            user_id="service-account",
            roles=("service", "owner"),
            display_name="service",
            auth_method="api_key",
        )

    def _maybe_bearer(self, headers: "HeaderLike") -> str:
        auth = headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            return auth[7:].strip()
        return ""


class HeaderLike:
    """Minimal case-insensitive header accessor (Starlette headers satisfy this)."""

    def get(self, key: str, default: str = "") -> str:  # pragma: no cover - protocol
        raise NotImplementedError


__all__ = ["IdentityExtractor"]
