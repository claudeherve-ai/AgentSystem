"""Artifact store: local filesystem (dev/test) and async Azure Blob (prod).

The store owns only the *bytes*. Metadata (name, content type, size, owning
run/workspace) lives in SQL via :class:`~agentsystem.repositories.ArtifactRepository`.
Responses never contain SAS URLs or secrets — download is proxied through the
API using the stored ``storage_backend`` + ``storage_key``.
"""

from __future__ import annotations

import hashlib
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from agentsystem.errors import DependencyUnavailableError
from agentsystem.settings import Settings, get_settings

logger = logging.getLogger("agentsystem.artifacts")


@dataclass(frozen=True, slots=True)
class StoredArtifact:
    """Result of persisting bytes to a backend."""

    backend: str
    key: str
    size_bytes: int
    sha256: str


class ArtifactStore(ABC):
    """Backend-agnostic artifact byte store."""

    backend_name: str = "abstract"

    @abstractmethod
    async def put(self, key: str, data: bytes) -> StoredArtifact:
        ...

    @abstractmethod
    async def get(self, key: str) -> bytes:
        ...

    @abstractmethod
    async def health(self) -> bool:
        ...


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class LocalArtifactStore(ArtifactStore):
    """Filesystem-backed store for dev/test. Keys map to files under a root."""

    backend_name = "local"

    def __init__(self, root: str) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        # Prevent path traversal: keys are flattened to a safe filename.
        safe = key.replace("\\", "/").strip("/").replace("..", "_")
        target = (self._root / safe).resolve()
        if self._root.resolve() not in target.parents and target != self._root.resolve():
            raise DependencyUnavailableError("invalid artifact key")
        return target

    async def put(self, key: str, data: bytes) -> StoredArtifact:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return StoredArtifact(
            backend=self.backend_name,
            key=key,
            size_bytes=len(data),
            sha256=_sha256(data),
        )

    async def get(self, key: str) -> bytes:
        path = self._path(key)
        if not path.exists():
            raise DependencyUnavailableError("artifact not found in store")
        return path.read_bytes()

    async def health(self) -> bool:
        try:
            return self._root.exists() and self._root.is_dir()
        except OSError:  # pragma: no cover - platform dependent
            return False


class BlobArtifactStore(ArtifactStore):
    """Azure Blob Storage store using managed identity (DefaultAzureCredential).

    No account keys or SAS tokens are used. The async credential and client are
    created lazily and closed after each operation-cluster via ``aclose``.
    """

    backend_name = "blob"

    def __init__(self, account_url: str, container: str) -> None:
        if not account_url:
            raise DependencyUnavailableError("blob account url not configured")
        self._account_url = account_url
        self._container = container

    async def _client(self):
        from azure.identity.aio import DefaultAzureCredential
        from azure.storage.blob.aio import BlobServiceClient

        credential = DefaultAzureCredential()
        service = BlobServiceClient(
            account_url=self._account_url, credential=credential
        )
        return service, credential

    async def put(self, key: str, data: bytes) -> StoredArtifact:
        service, credential = await self._client()
        try:
            container = service.get_container_client(self._container)
            try:
                await container.create_container()
            except Exception:  # noqa: BLE001 - already exists is fine
                pass
            blob = container.get_blob_client(key)
            await blob.upload_blob(data, overwrite=True)
        finally:
            await service.close()
            await credential.close()
        return StoredArtifact(
            backend=self.backend_name,
            key=key,
            size_bytes=len(data),
            sha256=_sha256(data),
        )

    async def get(self, key: str) -> bytes:
        service, credential = await self._client()
        try:
            blob = service.get_blob_client(self._container, key)
            stream = await blob.download_blob()
            return await stream.readall()
        finally:
            await service.close()
            await credential.close()

    async def health(self) -> bool:
        service, credential = await self._client()
        try:
            container = service.get_container_client(self._container)
            await container.get_container_properties()
            return True
        except Exception:  # noqa: BLE001 - health probe must not raise
            return False
        finally:
            await service.close()
            await credential.close()


_store: Optional[ArtifactStore] = None


def build_artifact_store(settings: Optional[Settings] = None) -> ArtifactStore:
    """Construct the configured artifact store.

    In production, selecting ``blob`` without a configured account URL raises so
    startup/readiness fails closed rather than silently using local files.
    """
    settings = settings or get_settings()
    if settings.artifact_is_blob:
        if not settings.blob_account_url:
            raise DependencyUnavailableError(
                "ARTIFACT_MODE=blob requires BLOB_ACCOUNT_URL"
            )
        return BlobArtifactStore(settings.blob_account_url, settings.blob_container)
    if settings.is_production and settings.artifact_mode == "local":
        logger.warning(
            "ARTIFACT_MODE=local in production — artifacts are not durable "
            "across replicas. Set ARTIFACT_MODE=blob."
        )
    return LocalArtifactStore(settings.artifact_local_root)


def get_artifact_store() -> ArtifactStore:
    global _store
    if _store is None:
        _store = build_artifact_store()
    return _store


def set_artifact_store(store: Optional[ArtifactStore]) -> None:
    """Inject/replace the process artifact store (tests)."""
    global _store
    _store = store


__all__ = [
    "ArtifactStore",
    "BlobArtifactStore",
    "LocalArtifactStore",
    "StoredArtifact",
    "build_artifact_store",
    "get_artifact_store",
    "set_artifact_store",
]
