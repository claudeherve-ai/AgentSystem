from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from agentsystem.durable import DurableTaskExecutor
from agentsystem.sandbox import DynamicSessionsInterpreter


pytestmark = pytest.mark.asyncio


class _DurableClient:
    def __init__(self) -> None:
        self.instance_id = ""

    def get_orchestration_state(self, instance_id: str):
        self.instance_id = instance_id
        return None


async def test_durable_health_performs_scheduler_query():
    executor = DurableTaskExecutor("https://scheduler.test", "hub")
    client = _DurableClient()
    executor._client = client

    assert await executor.health() is True
    assert client.instance_id == "__agentsystem_health_probe__"


class _Response:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        self.is_success = 200 <= status_code < 300


class _HttpClient:
    response = _Response(200)
    last_url = ""
    last_headers: dict[str, str] = {}

    def __init__(self, **_kwargs) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def get(self, url: str, *, headers: dict[str, str]):
        type(self).last_url = url
        type(self).last_headers = headers
        return type(self).response


async def test_dynamic_sessions_health_probes_authenticated_data_plane(monkeypatch):
    import httpx

    interpreter = DynamicSessionsInterpreter("https://sessions.test")
    monkeypatch.setattr(interpreter, "_token", AsyncMock(return_value="signed-token"))
    monkeypatch.setattr(httpx, "AsyncClient", _HttpClient)
    _HttpClient.response = _Response(404)

    assert await interpreter.health() is True
    assert "/session?" in _HttpClient.last_url
    assert _HttpClient.last_headers["Authorization"] == "Bearer signed-token"


async def test_dynamic_sessions_health_rejects_authorization_failure(monkeypatch):
    import httpx

    interpreter = DynamicSessionsInterpreter("https://sessions.test")
    monkeypatch.setattr(interpreter, "_token", AsyncMock(return_value="signed-token"))
    monkeypatch.setattr(httpx, "AsyncClient", _HttpClient)
    _HttpClient.response = _Response(403)

    assert await interpreter.health() is False
