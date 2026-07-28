from __future__ import annotations

import asyncio
from typing import Any

from src.chatbot.service import ChatSettings


def settings(**overrides: Any) -> ChatSettings:
    values = {
        "api_key": "test-key-not-real",
        "model": "gemini-test",
        "timeout_seconds": 1.0,
        "max_message_chars": 100,
        "session_ttl_seconds": 60,
        "max_sessions": 20,
        "max_tool_rounds": 4,
        "rate_limit_per_minute": 20,
    }
    values.update(overrides)
    return ChatSettings(**values)


def response(
    interaction_id: str,
    *,
    text: str | None = None,
    call: tuple[str, str, dict[str, Any]] | None = None,
    status: str = "completed",
    tokens: int = 3,
) -> dict[str, Any]:
    steps: list[dict[str, Any]] = [{"type": "thought", "signature": "hidden"}]
    if call:
        steps.append(
            {
                "type": "function_call",
                "name": call[0],
                "id": call[1],
                "arguments": call[2],
            }
        )
    if text is not None:
        steps.append(
            {
                "type": "model_output",
                "content": [{"type": "text", "text": text}],
            }
        )
    return {
        "id": interaction_id,
        "status": status,
        "steps": steps,
        "usage": {
            "total_input_tokens": 1,
            "total_output_tokens": 2,
            "total_tokens": tokens,
        },
    }


class FakeGateway:
    def __init__(
        self,
        create_results: list[Any] | None = None,
        stream_results: list[Any] | None = None,
    ) -> None:
        self.create_results = list(create_results or [])
        self.stream_results = list(stream_results or [])
        self.create_requests: list[dict[str, Any]] = []
        self.stream_requests: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> Any:
        self.create_requests.append(kwargs)
        result = self.create_results.pop(0)
        if isinstance(result, BaseException):
            raise result
        if callable(result):
            result = result()
        if asyncio.iscoroutine(result):
            return await result
        return result

    async def stream(self, **kwargs: Any):
        self.stream_requests.append(kwargs)
        result = self.stream_results.pop(0)
        if isinstance(result, BaseException):
            raise result
        for event in result:
            if isinstance(event, BaseException):
                raise event
            yield event


class FakeTools:
    declarations = [
        {
            "type": "function",
            "name": "eco_tool",
            "description": "test",
            "parameters": {"type": "object", "additionalProperties": False},
        }
    ]

    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []

    async def execute(self, name: str, arguments: Any) -> dict[str, Any]:
        self.calls.append((name, arguments))
        if name != "eco_tool":
            return {
                "ok": False,
                "error": {"code": "TOOL_NOT_ALLOWED", "message": "nao permitida"},
            }
        return {"ok": True, "data": {"altura_cm": 12.3}}


def direct_stream(interaction_id: str = "stream-final", text: str = "Ola"):
    return [
        {
            "event_type": "interaction.created",
            "interaction": {"id": interaction_id, "status": "in_progress"},
        },
        {
            "event_type": "step.start",
            "index": 0,
            "step": {"type": "thought"},
        },
        {
            "event_type": "step.delta",
            "index": 0,
            "delta": {"type": "thought_signature", "signature": "secret"},
        },
        {
            "event_type": "step.start",
            "index": 1,
            "step": {"type": "model_output"},
        },
        {
            "event_type": "step.delta",
            "index": 1,
            "delta": {"type": "text", "text": text},
        },
        {
            "event_type": "interaction.completed",
            "interaction": {
                "id": interaction_id,
                "status": "completed",
                "usage": {"total_tokens": 4},
            },
        },
    ]
