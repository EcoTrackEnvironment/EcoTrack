from __future__ import annotations

import asyncio

import pytest

from src.chatbot.service import ChatService, ChatServiceError

from .chatbot_fakes import (
    FakeGateway,
    FakeTools,
    direct_stream,
    response,
    settings,
)


@pytest.mark.asyncio
async def test_direct_response_and_context_reuse():
    gateway = FakeGateway(
        [response("i1", text="Primeira"), response("i2", text="Segunda")]
    )
    service = ChatService(settings(), gateway=gateway)

    first = await service.chat("Oi", None)
    second = await service.chat("Continue", first.conversation_id)

    assert first.message == "Primeira"
    assert second.message == "Segunda"
    assert "previous_interaction_id" not in gateway.create_requests[0]
    assert gateway.create_requests[1]["previous_interaction_id"] == "i1"
    assert gateway.create_requests[0]["system_instruction"]
    assert gateway.create_requests[1]["tools"] == gateway.create_requests[0]["tools"]


@pytest.mark.asyncio
async def test_function_call_uses_call_id_and_updates_only_final_interaction():
    gateway = FakeGateway(
        [
            response(
                "tool-request",
                call=("eco_tool", "call-123", {"ponto": "RA-S01"}),
                status="requires_action",
            ),
            response("final", text="Altura estimada: 12,3 cm."),
        ]
    )
    tools = FakeTools()
    service = ChatService(settings(), gateway=gateway, tools=tools)

    result = await service.chat("Consulte", None)

    assert result.message.startswith("Altura")
    assert tools.calls == [("eco_tool", {"ponto": "RA-S01"})]
    function_result = gateway.create_requests[1]["input"][0]
    assert function_result["call_id"] == "call-123"
    assert function_result["name"] == "eco_tool"
    session = await service.sessions.get(result.conversation_id)
    assert session.previous_interaction_id == "final"


@pytest.mark.asyncio
async def test_multiple_tool_rounds_and_usage_sum():
    gateway = FakeGateway(
        [
            response("t1", call=("eco_tool", "c1", {}), status="requires_action"),
            response("t2", call=("eco_tool", "c2", {}), status="requires_action"),
            response("done", text="Pronto"),
        ]
    )
    tools = FakeTools()
    service = ChatService(settings(), gateway=gateway, tools=tools)

    result = await service.chat("Consulte", None)

    assert len(tools.calls) == 2
    assert result.usage.total_tokens == 9


@pytest.mark.asyncio
async def test_unknown_tool_is_not_executed_arbitrarily():
    gateway = FakeGateway(
        [
            response(
                "bad-tool",
                call=("shell", "c1", {"command": "no"}),
                status="requires_action",
            ),
            response("done", text="Ferramenta indisponivel."),
        ]
    )
    tools = FakeTools()
    service = ChatService(settings(), gateway=gateway, tools=tools)

    await service.chat("Execute", None)

    assert tools.calls[0][0] == "shell"
    sent = gateway.create_requests[1]["input"][0]["result"][0]["text"]
    assert "TOOL_NOT_ALLOWED" in sent
    assert "command" not in gateway.create_requests[1]


@pytest.mark.asyncio
async def test_tool_round_limit_stops_loop():
    gateway = FakeGateway(
        [
            response("t1", call=("eco_tool", "c1", {}), status="requires_action"),
            response("t2", call=("eco_tool", "c2", {}), status="requires_action"),
        ]
    )
    service = ChatService(
        settings(max_tool_rounds=1),
        gateway=gateway,
        tools=FakeTools(),
    )

    with pytest.raises(ChatServiceError, match="etapas demais") as caught:
        await service.chat("loop", None)
    assert caught.value.code == "TOOL_ROUND_LIMIT"


@pytest.mark.asyncio
async def test_retries_429_before_output():
    class RateError(Exception):
        status_code = 429

    gateway = FakeGateway([RateError(), response("ok", text="recuperou")])
    delays: list[float] = []

    async def no_sleep(delay: float) -> None:
        delays.append(delay)

    service = ChatService(
        settings(),
        gateway=gateway,
        sleep=no_sleep,
        jitter=lambda: 0,
    )
    result = await service.chat("Oi", None)

    assert result.message == "recuperou"
    assert len(gateway.create_requests) == 2
    assert delays == [0.25]


@pytest.mark.asyncio
async def test_timeout_and_blocked_content_do_not_commit_session():
    async def slow():
        await asyncio.sleep(0.05)
        return response("late", text="tarde")

    gateway = FakeGateway([slow, slow, slow])

    async def no_sleep(_: float) -> None:
        return None

    service = ChatService(
        settings(timeout_seconds=0.001),
        gateway=gateway,
        sleep=no_sleep,
    )
    session = await service.resolve_session(None)
    with pytest.raises(ChatServiceError) as timeout:
        await service.chat("Oi", session.conversation_id)
    assert timeout.value.code == "PROVIDER_TIMEOUT"
    assert session.previous_interaction_id is None

    blocked_gateway = FakeGateway([response("blocked", status="blocked")])
    blocked = ChatService(settings(), gateway=blocked_gateway)
    with pytest.raises(ChatServiceError) as safety:
        await blocked.chat("conteudo", None)
    assert safety.value.code == "CONTENT_BLOCKED"


@pytest.mark.asyncio
async def test_stream_retries_before_delta_but_never_after_visible_output():
    class RateError(Exception):
        status_code = 429

    async def no_sleep(_: float) -> None:
        return None

    retry_gateway = FakeGateway(
        stream_results=[[RateError()], direct_stream(text="recuperou")]
    )
    retry_service = ChatService(
        settings(),
        gateway=retry_gateway,
        sleep=no_sleep,
    )
    retry_session = await retry_service.resolve_session(None)
    events = [
        event
        async for event in retry_service.stream_chat("Oi", retry_session)
    ]
    assert [event.event for event in events] == ["session", "delta", "done"]
    assert len(retry_gateway.stream_requests) == 2

    visible_then_error = [
        {
            "event_type": "interaction.created",
            "interaction": {"id": "partial"},
        },
        {
            "event_type": "step.start",
            "index": 0,
            "step": {"type": "model_output"},
        },
        {
            "event_type": "step.delta",
            "index": 0,
            "delta": {"type": "text", "text": "parcial"},
        },
        RateError(),
    ]
    no_retry_gateway = FakeGateway(stream_results=[visible_then_error])
    no_retry_service = ChatService(
        settings(),
        gateway=no_retry_gateway,
        sleep=no_sleep,
    )
    no_retry_session = await no_retry_service.resolve_session(None)
    received = []
    with pytest.raises(ChatServiceError) as caught:
        async for event in no_retry_service.stream_chat("Oi", no_retry_session):
            received.append(event.event)
    assert caught.value.code == "RATE_LIMITED"
    assert received == ["session", "delta"]
    assert len(no_retry_gateway.stream_requests) == 1
    assert no_retry_session.previous_interaction_id is None


@pytest.mark.asyncio
async def test_concurrent_turns_in_same_conversation_are_serialized():
    class OrderedGateway:
        def __init__(self):
            self.active = 0
            self.max_active = 0
            self.requests = []
            self.count = 0

        async def create(self, **kwargs):
            self.requests.append(kwargs)
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            await asyncio.sleep(0.01)
            self.count += 1
            current = self.count
            self.active -= 1
            return response(f"ordered-{current}", text=f"turno {current}")

        async def stream(self, **kwargs):
            if False:
                yield kwargs

    gateway = OrderedGateway()
    service = ChatService(settings(), gateway=gateway)
    session = await service.resolve_session(None)

    first, second = await asyncio.gather(
        service.chat("primeiro", session.conversation_id),
        service.chat("segundo", session.conversation_id),
    )

    assert {first.message, second.message} == {"turno 1", "turno 2"}
    assert gateway.max_active == 1
    assert gateway.requests[1]["previous_interaction_id"] == "ordered-1"
    assert session.previous_interaction_id == "ordered-2"
