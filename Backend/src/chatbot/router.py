"""Rotas HTTP/SSE do chatbot."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import defaultdict, deque

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from .schemas import (
    ChatRequest,
    ChatResponse,
    ConversationDeleteResponse,
    StreamEvent,
)
from .service import ChatService, ChatServiceError

logger = logging.getLogger("ecotrack.chatbot.router")


class InMemoryRateLimiter:
    def __init__(self, limit: int, clock=time.monotonic) -> None:
        self._limit = limit
        self._clock = clock
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def check(self, key: str) -> None:
        async with self._lock:
            now = self._clock()
            hits = self._hits[key]
            while hits and hits[0] <= now - 60:
                hits.popleft()
            if len(hits) >= self._limit:
                raise ChatServiceError(
                    "RATE_LIMITED",
                    "Limite temporariamente atingido.",
                    429,
                    retryable=True,
                )
            hits.append(now)


def _raise_http(error: ChatServiceError) -> None:
    raise HTTPException(
        status_code=error.http_status,
        detail={
            "code": error.code,
            "message": error.public_message,
            "retryable": error.retryable,
        },
    )


def _sse(event: StreamEvent) -> str:
    return (
        f"event: {event.event}\n"
        f"data: {json.dumps(event.data, ensure_ascii=False, separators=(',', ':'))}\n\n"
    )


def _client_identity(request: Request) -> str:
    # X-Forwarded-For e ignorado por padrao: so deve ser confiado quando a
    # infraestrutura tiver um proxy confiavel configurado.
    return request.client.host if request.client else "unknown"


def create_chat_router(
    service: ChatService | None = None,
    rate_limiter: InMemoryRateLimiter | None = None,
) -> APIRouter:
    service = service or ChatService.from_environment()
    limiter = rate_limiter or InMemoryRateLimiter(
        service.settings.rate_limit_per_minute
    )
    router = APIRouter(prefix="/chat", tags=["chatbot"])

    @router.post("", response_model=ChatResponse)
    async def chat(payload: ChatRequest, request: Request) -> ChatResponse:
        try:
            service.ensure_configured()
            await limiter.check(_client_identity(request))
            return await service.chat(payload.message, payload.conversation_id)
        except ChatServiceError as error:
            _raise_http(error)

    @router.post("/stream")
    async def chat_stream(payload: ChatRequest, request: Request) -> StreamingResponse:
        try:
            service.ensure_configured()
            clean = service.validate_message(payload.message)
            await limiter.check(_client_identity(request))
            session = await service.resolve_session(payload.conversation_id)
        except ChatServiceError as error:
            _raise_http(error)

        async def events():
            terminal = False
            stream = service.stream_chat(clean, session)
            try:
                async for event in stream:
                    if await request.is_disconnected():
                        await stream.aclose()
                        return
                    if event.event in {"done", "error"}:
                        if terminal:
                            return
                        terminal = True
                    yield _sse(event)
            except asyncio.CancelledError:
                await stream.aclose()
                raise
            except ChatServiceError as error:
                if not terminal:
                    terminal = True
                    yield _sse(
                        StreamEvent(
                            event="error",
                            data={
                                "code": error.code,
                                "message": error.public_message,
                                "retryable": error.retryable,
                            },
                        )
                    )
            except Exception:
                logger.exception("chat_stream_unexpected_error")
                if not terminal:
                    yield _sse(
                        StreamEvent(
                            event="error",
                            data={
                                "code": "INTERNAL_ERROR",
                                "message": "Falha temporaria ao gerar a resposta.",
                                "retryable": False,
                            },
                        )
                    )

        return StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-store",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    @router.delete(
        "/conversations/{conversation_id}",
        response_model=ConversationDeleteResponse,
    )
    async def delete_conversation(conversation_id: str) -> ConversationDeleteResponse:
        await service.sessions.delete(conversation_id)
        return ConversationDeleteResponse(conversation_id=conversation_id)

    return router
