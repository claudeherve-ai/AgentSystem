from __future__ import annotations

import pytest

from tools import rag_store


def test_embeddings_enabled_with_entra_and_no_key(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://resource.example.com")
    monkeypatch.setenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "embedding")
    monkeypatch.setenv("AZURE_OPENAI_USE_ENTRA", "true")
    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)

    assert rag_store.embeddings_enabled() is True


@pytest.mark.asyncio
async def test_embedding_uses_entra_bearer_token(monkeypatch):
    captured: dict = {}

    class Credential:
        def __init__(self, **kwargs):
            captured["credential_kwargs"] = kwargs

        async def get_token(self, scope):
            captured["scope"] = scope
            return type("Token", (), {"token": "test-token"})()

        async def close(self):
            captured["credential_closed"] = True

    class Response:
        status_code = 200

        @staticmethod
        def json():
            return {"data": [{"embedding": [0.5, 0.25]}]}

    class Client:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, url, *, headers, json):
            captured.update(url=url, headers=headers, json=json)
            return Response()

    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://resource.example.com")
    monkeypatch.setenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "embedding")
    monkeypatch.setenv("AZURE_OPENAI_USE_ENTRA", "true")
    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
    monkeypatch.setattr("azure.identity.aio.DefaultAzureCredential", Credential)
    monkeypatch.setattr(rag_store.httpx, "AsyncClient", Client)

    result = await rag_store._embed_text("hello")

    assert result == [0.5, 0.25]
    assert captured["headers"]["Authorization"] == "Bearer test-token"
    assert "api-key" not in captured["headers"]
    assert captured["scope"] == "https://cognitiveservices.azure.com/.default"
    assert captured["credential_closed"] is True
