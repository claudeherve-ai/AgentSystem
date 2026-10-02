from __future__ import annotations

from types import SimpleNamespace

import pytest

from agentsystem.context import RunContext
from api.routes.chat import ChatAcceptedResponse, ChatRequest, ChatResponse, chat


class _Service:
    def __init__(self, mode: str):
        self.execution_mode = mode
        self.created = 0
        self.executed = 0

    async def create_run(self, ctx, **_kwargs):
        self.created += 1
        return SimpleNamespace(
            id=ctx.run_id,
            session_id=ctx.session_id,
            status="pending",
        )

    async def execute(self, _ctx):
        self.executed += 1

    async def create_and_execute(self, ctx, **_kwargs):
        self.executed += 1
        return SimpleNamespace(
            id=ctx.run_id,
            session_id=ctx.session_id,
            output_text="done",
            selected_agent="EngineeringAgent",
        )


@pytest.fixture
def route_context(monkeypatch):
    ctx = RunContext.for_local(session_id="session-1", run_id="run-1")

    async def resolve(_request, *, session_id=None):
        assert session_id in (None, "session-1")
        return ctx

    monkeypatch.setattr("api.routes.chat.resolve_context", resolve)
    return ctx


@pytest.mark.asyncio
async def test_dts_chat_returns_truthful_accepted_contract(
    monkeypatch, route_context
):
    service = _Service("dts")
    monkeypatch.setattr("api.routes.chat.get_run_service", lambda: service)

    response = await chat(
        SimpleNamespace(),
        ChatRequest(message="build it", session_id="session-1"),
    )

    assert response.status_code == 202
    accepted = ChatAcceptedResponse.model_validate_json(response.body)
    assert accepted.run_id == "run-1"
    assert accepted.status == "pending"
    assert accepted.status_url == "/api/v1/runs/run-1"
    assert accepted.events_url == "/api/v1/runs/run-1/events"
    assert service.created == 1
    assert service.executed == 1


@pytest.mark.asyncio
async def test_local_chat_preserves_synchronous_response(
    monkeypatch, route_context
):
    service = _Service("local")
    monkeypatch.setattr("api.routes.chat.get_run_service", lambda: service)

    response = await chat(
        SimpleNamespace(),
        ChatRequest(message="build it", session_id="session-1"),
    )

    assert isinstance(response, ChatResponse)
    assert response.response == "done"
    assert response.selected_agent == "EngineeringAgent"
    assert service.created == 0
    assert service.executed == 1
