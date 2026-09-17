from __future__ import annotations

from contextlib import asynccontextmanager

import httpx
import pytest
from fastapi import FastAPI

from src.chatbot.router import InMemoryRateLimiter, create_chat_router
from src.chatbot.service import ChatService
from src.chatbot.sessions import InMemorySessionStore

from .chatbot_fakes import FakeGateway, direct_stream, response, settings


@asynccontextmanager
async def client_for(
    service: ChatService,
    limiter: InMemoryRateLimiter | None = None,
) -> httpx.AsyncClient:
    app = FastAPI()
    app.include_router(create_chat_router(service, limiter))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield client


@pytest.mark.asyncio
async def test_api_creates_conversation_and_reuses_context():
    gateway = FakeGateway(
        [response("api-1", text="Ola"), response("api-2", text="Contexto mantido")]
    )
    service = ChatService(settings(), gateway=gateway)
    async with client_for(service) as client:
        first = await client.post(
            "/chat", json={"message": "Oi", "conversation_id": None}
        )
        conversation_id = first.json()["conversation_id"]
        second = await client.post(
            "/chat",
            json={"message": "Continue", "conversation_id": conversation_id},
        )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["message"] == "Contexto mantido"
    assert gateway.create_requests[1]["previous_interaction_id"] == "api-1"
    assert "api-1" not in second.text


@pytest.mark.asyncio
async def test_api_validates_empty_long_and_unknown_conversation():
    service = ChatService(settings(max_message_chars=5), gateway=FakeGateway())
    async with client_for(service) as client:
        assert (await client.post("/chat", json={"message": "   "})).status_code == 422
        assert (
            await client.post("/chat", json={"message": "123456"})
        ).status_code == 422
        unknown = await client.post(
            "/chat",
            json={"message": "Oi", "conversation_id": "x" * 43},
        )
    assert unknown.status_code == 404
    assert unknown.json()["detail"]["code"] == "CONVERSATION_NOT_FOUND"


@pytest.mark.asyncio
async def test_api_rejects_expired_conversation():
    now = [10.0]
    store = InMemorySessionStore(5, 10, clock=lambda: now[0])
    gateway = FakeGateway([response("first", text="ok")])
    service = ChatService(settings(), gateway=gateway, sessions=store)
    async with client_for(service) as client:
        created = (await client.post("/chat", json={"message": "Oi"})).json()[
            "conversation_id"
        ]
        now[0] = 20.0
        expired = await client.post(
            "/chat",
            json={"message": "Oi", "conversation_id": created},
        )
    assert expired.status_code == 404


@pytest.mark.asyncio
async def test_missing_key_only_disables_chatbot():
    service = ChatService(settings(api_key=""), gateway=None)
    async with client_for(service) as client:
        result = await client.post("/chat", json={"message": "Oi"})

    assert result.status_code == 503
    assert result.json()["detail"]["code"] == "CHAT_NOT_CONFIGURED"


@pytest.mark.asyncio
async def test_local_rate_limit():
    gateway = FakeGateway([response("one", text="ok")])
    service = ChatService(settings(rate_limit_per_minute=1), gateway=gateway)
    async with client_for(service, InMemoryRateLimiter(1)) as client:
        assert (await client.post("/chat", json={"message": "Oi"})).status_code == 200
        limited = await client.post("/chat", json={"message": "De novo"})
    assert limited.status_code == 429
    assert limited.json()["detail"]["retryable"] is True


@pytest.mark.asyncio
async def test_delete_clears_only_local_conversation():
    gateway = FakeGateway([response("one", text="ok")])
    service = ChatService(settings(), gateway=gateway)
    async with client_for(service) as client:
        conversation_id = (await client.post("/chat", json={"message": "Oi"})).json()[
            "conversation_id"
        ]
        deleted = await client.delete(f"/chat/conversations/{conversation_id}")
        reused = await client.post(
            "/chat",
            json={"message": "Oi", "conversation_id": conversation_id},
        )

    assert deleted.status_code == 200
    assert deleted.json() == {
        "conversation_id": conversation_id,
        "cleared": True,
        "remote_deleted": False,
    }
    assert reused.status_code == 404


@pytest.mark.asyncio
async def test_sse_contract_filters_thought_events():
    gateway = FakeGateway(stream_results=[direct_stream(text="Resposta segura")])
    service = ChatService(settings(), gateway=gateway)
    async with client_for(service) as client:
        response_http = await client.post("/chat/stream", json={"message": "Oi"})

    assert response_http.status_code == 200
    assert response_http.headers["content-type"].startswith("text/event-stream")
    assert response_http.text.count("event: session") == 1
    assert response_http.text.count("event: delta") == 1
    assert response_http.text.count("event: done") == 1
    assert "Resposta segura" in response_http.text
    assert "thought" not in response_http.text
    assert "signature" not in response_http.text
    assert "stream-final" not in response_http.text


@pytest.mark.asyncio
async def test_sse_function_call_emits_sanitized_status_then_final_text():
    tool_stream = [
        {
            "event_type": "interaction.created",
            "interaction": {"id": "tool-interaction"},
        },
        {
            "event_type": "step.start",
            "index": 0,
            "step": {"type": "function_call", "name": "eco_tool", "id": "call-9"},
        },
        {
            "event_type": "step.delta",
            "index": 0,
            "delta": {"type": "arguments_delta", "arguments": "{}"},
        },
        {
            "event_type": "interaction.completed",
            "interaction": {
                "id": "tool-interaction",
                "status": "requires_action",
                "usage": {"total_tokens": 2},
            },
        },
    ]
    gateway = FakeGateway(
        stream_results=[tool_stream, direct_stream("final-interaction", "12,3 cm")]
    )
    service = ChatService(settings(), gateway=gateway)
    async with client_for(service) as client:
        result = await client.post("/chat/stream", json={"message": "Consulte"})

    assert result.status_code == 200
    assert "event: status" in result.text
    assert '"tool":"eco_tool"' in result.text
    assert "call-9" not in result.text
    assert "12,3 cm" in result.text
    assert result.text.count("event: done") == 1
