"""Orquestracao da Interactions API, function calling e streaming seguro."""

from __future__ import annotations

import asyncio
import datetime as dt
import email.utils
import json
import logging
import random
import time
import uuid
from dataclasses import dataclass
from typing import Any, AsyncIterator, Awaitable, Callable, Protocol

from .. import config
from .prompts import SYSTEM_INSTRUCTION
from .schemas import ChatResponse, StreamEvent, TokenUsage
from .sessions import ChatSession, InMemorySessionStore, SessionNotFoundError, SessionStore
from .tools import ToolRegistry

logger = logging.getLogger("ecotrack.chatbot.service")

def _value(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


@dataclass(frozen=True)
class ChatSettings:
    api_key: str
    model: str
    timeout_seconds: float
    max_message_chars: int
    session_ttl_seconds: int
    max_sessions: int
    max_tool_rounds: int
    rate_limit_per_minute: int

    @classmethod
    def from_environment(cls) -> "ChatSettings":
        return cls(
            api_key=config.GEMINI_API_KEY,
            model=config.GEMINI_MODEL,
            timeout_seconds=config.GEMINI_TIMEOUT_SECONDS,
            max_message_chars=config.CHAT_MAX_MESSAGE_CHARS,
            session_ttl_seconds=config.CHAT_SESSION_TTL_SECONDS,
            max_sessions=config.CHAT_MAX_SESSIONS,
            max_tool_rounds=config.CHAT_MAX_TOOL_ROUNDS,
            rate_limit_per_minute=config.CHAT_RATE_LIMIT_PER_MINUTE,
        )


class InteractionGateway(Protocol):
    async def create(self, **kwargs: Any) -> Any: ...

    def stream(self, **kwargs: Any) -> AsyncIterator[Any]: ...


class GoogleInteractionsGateway:
    """Adaptador pequeno e injetavel para o SDK oficial google-genai."""

    def __init__(self, api_key: str, timeout_seconds: float) -> None:
        from google import genai

        self._client = genai.Client(
            api_key=api_key,
            http_options={"timeout": int(timeout_seconds * 1000)},
        )

    async def create(self, **kwargs: Any) -> Any:
        return await self._client.aio.interactions.create(**kwargs)

    async def stream(self, **kwargs: Any) -> AsyncIterator[Any]:
        raw_stream = await self._client.aio.interactions.create(
            stream=True,
            **kwargs,
        )
        try:
            async for item in raw_stream:
                yield item
        finally:
            close = getattr(raw_stream, "close", None)
            if callable(close):
                try:
                    await close()
                except Exception:
                    logger.warning("chatbot_stream_close_failed")


class ChatServiceError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        http_status: int,
        *,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.public_message = message
        self.http_status = http_status
        self.retryable = retryable


def _provider_error(exc: BaseException) -> ChatServiceError:
    if isinstance(exc, ChatServiceError):
        return exc
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
        return ChatServiceError(
            "PROVIDER_TIMEOUT",
            "O servico demorou alem do limite.",
            504,
            retryable=True,
        )
    status = _value(exc, "status_code") or _value(exc, "code")
    code_text = str(_value(exc, "code", "")).lower()
    if "safety" in code_text or "blocked" in code_text:
        return ChatServiceError(
            "CONTENT_BLOCKED",
            "A solicitacao foi bloqueada pelos filtros de seguranca.",
            422,
        )
    try:
        status = int(status)
    except (TypeError, ValueError):
        status = None
    if status == 429:
        return ChatServiceError(
            "RATE_LIMITED",
            "Limite temporariamente atingido.",
            429,
            retryable=True,
        )
    if status in {401, 403}:
        return ChatServiceError(
            "PROVIDER_AUTH_CONFIG",
            "A configuracao do chatbot esta invalida.",
            503,
        )
    if status == 404:
        return ChatServiceError(
            "MODEL_UNAVAILABLE",
            "O modelo do chatbot esta temporariamente indisponivel.",
            503,
        )
    if status in {408, 504}:
        return ChatServiceError(
            "PROVIDER_TIMEOUT",
            "O servico demorou alem do limite.",
            504,
            retryable=True,
        )
    if status is not None and status >= 500:
        return ChatServiceError(
            "PROVIDER_UNAVAILABLE",
            "Falha temporaria ao gerar a resposta.",
            502,
            retryable=True,
        )
    return ChatServiceError(
        "PROVIDER_ERROR",
        "Falha temporaria ao gerar a resposta.",
        502,
    )


def _usage(raw: Any) -> TokenUsage:
    if raw is None:
        return TokenUsage()
    return TokenUsage(
        input_tokens=_value(raw, "total_input_tokens", _value(raw, "input_tokens")),
        output_tokens=_value(raw, "total_output_tokens", _value(raw, "output_tokens")),
        total_tokens=_value(raw, "total_tokens"),
    )


def _model_text(steps: list[Any]) -> str:
    parts: list[str] = []
    for step in steps:
        if _value(step, "type") != "model_output":
            continue
        for block in _value(step, "content", []) or []:
            if _value(block, "type") == "text":
                text = _value(block, "text", "")
                if text:
                    parts.append(str(text))
    return "".join(parts)


def _function_calls(steps: list[Any]) -> list[dict[str, Any]]:
    calls = []
    for step in steps:
        if _value(step, "type") != "function_call":
            continue
        arguments = _value(step, "arguments", {}) or {}
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                arguments = {"_invalid_json": True}
        calls.append(
            {
                "name": _value(step, "name", ""),
                "call_id": _value(step, "id", ""),
                "arguments": arguments,
            }
        )
    return calls


def _retry_after_seconds(exc: BaseException) -> float | None:
    response = _value(exc, "response")
    headers = _value(response, "headers", {}) or _value(exc, "headers", {}) or {}
    value = headers.get("retry-after") or headers.get("Retry-After")
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        try:
            parsed = email.utils.parsedate_to_datetime(str(value))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=dt.timezone.utc)
            return max(0.0, (parsed - dt.datetime.now(dt.timezone.utc)).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return None


class ChatService:
    def __init__(
        self,
        settings: ChatSettings,
        gateway: InteractionGateway | None = None,
        sessions: SessionStore | None = None,
        tools: ToolRegistry | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        jitter: Callable[[], float] = random.random,
    ) -> None:
        self.settings = settings
        self.gateway = gateway
        self.sessions = sessions or InMemorySessionStore(
            settings.session_ttl_seconds,
            settings.max_sessions,
        )
        self.tools = tools or ToolRegistry()
        self._sleep = sleep
        self._jitter = jitter

    @classmethod
    def from_environment(cls) -> "ChatService":
        settings = ChatSettings.from_environment()
        gateway: InteractionGateway | None = None
        if settings.api_key:
            try:
                gateway = GoogleInteractionsGateway(
                    settings.api_key,
                    settings.timeout_seconds,
                )
            except Exception as exc:
                logger.error(
                    "chatbot_provider_initialization_failed: %s: %s",
                    type(exc).__name__,
                    str(exc)[:200],
                )
                
        return cls(settings=settings, gateway=gateway)

    def ensure_configured(self) -> None:
        if not self.settings.api_key or self.gateway is None:
            raise ChatServiceError(
                "CHAT_NOT_CONFIGURED",
                "Chatbot temporariamente indisponivel.",
                503,
            )

    def validate_message(self, message: str) -> str:
        clean = message.strip()
        if not clean:
            raise ChatServiceError(
                "INVALID_MESSAGE",
                "A mensagem nao pode estar vazia.",
                422,
            )
        if len(clean) > self.settings.max_message_chars:
            raise ChatServiceError(
                "MESSAGE_TOO_LONG",
                f"A mensagem deve ter no maximo {self.settings.max_message_chars} caracteres.",
                422,
            )
        return clean

    async def resolve_session(self, conversation_id: str | None) -> ChatSession:
        if conversation_id is None:
            return await self.sessions.create()
        try:
            return await self.sessions.get(conversation_id)
        except SessionNotFoundError as exc:
            raise ChatServiceError(
                "CONVERSATION_NOT_FOUND",
                "Conversa ausente ou expirada. Inicie uma nova conversa.",
                404,
            ) from exc

    def _request(self, user_input: Any, previous_id: str | None) -> dict[str, Any]:
        request = {
            "model": self.settings.model,
            "input": user_input,
            "system_instruction": SYSTEM_INSTRUCTION,
            "tools": self.tools.declarations,
            "store": True,
        }
        if previous_id:
            request["previous_interaction_id"] = previous_id
        return request

    async def _retry_delay(
        self,
        attempt: int,
        retry_after: float | None = None,
    ) -> None:
        calculated = (0.25 * (2**attempt)) + (0.1 * self._jitter())
        await self._sleep(min(10.0, retry_after if retry_after is not None else calculated))

    async def _create(self, request: dict[str, Any]) -> Any:
        assert self.gateway is not None
        for attempt in range(3):
            try:
                return await asyncio.wait_for(
                    self.gateway.create(**request),
                    timeout=self.settings.timeout_seconds,
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                error = _provider_error(exc)
                if not error.retryable or attempt == 2:
                    raise error from exc
                await self._retry_delay(attempt, _retry_after_seconds(exc))
        raise AssertionError("retry loop exhausted")

    async def _execute_calls(
        self,
        calls: list[dict[str, Any]],
        correlation_id: str,
    ) -> list[dict[str, Any]]:
        results = []
        for call in calls:
            name = str(call["name"])
            call_id = str(call["call_id"])
            if not name or not call_id:
                raise ChatServiceError(
                    "INVALID_PROVIDER_RESPONSE",
                    "Falha temporaria ao gerar a resposta.",
                    502,
                )
            logger.info(
                "chat_tool_call",
                extra={"correlation_id": correlation_id, "tool": name},
            )
            result = await self.tools.execute(name, call["arguments"])
            results.append(
                {
                    "type": "function_result",
                    "name": name,
                    "call_id": call_id,
                    "result": [
                        {
                            "type": "text",
                            "text": json.dumps(
                                result,
                                ensure_ascii=False,
                                separators=(",", ":"),
                            ),
                        }
                    ],
                }
            )
        return results

    @staticmethod
    def _check_interaction(status: str | None, text: str, calls: list[Any]) -> None:
        if status in {"blocked", "rejected", "safety_blocked"}:
            raise ChatServiceError(
                "CONTENT_BLOCKED",
                "A solicitacao foi bloqueada pelos filtros de seguranca.",
                422,
            )
        if not calls and not text:
            raise ChatServiceError(
                "EMPTY_PROVIDER_RESPONSE",
                "Nao foi possivel gerar uma resposta segura.",
                502,
            )

    async def chat(self, message: str, conversation_id: str | None) -> ChatResponse:
        self.ensure_configured()
        clean = self.validate_message(message)
        session = await self.resolve_session(conversation_id)
        correlation_id = uuid.uuid4().hex
        started = time.perf_counter()
        usage = TokenUsage()
        async with session.turn_lock:
            current_input: Any = clean
            previous_id = session.previous_interaction_id
            tool_rounds = 0
            while True:
                interaction = await self._create(self._request(current_input, previous_id))
                steps = list(_value(interaction, "steps", []) or [])
                calls = _function_calls(steps)
                text = _model_text(steps)
                status = _value(interaction, "status")
                usage = usage.add(_usage(_value(interaction, "usage")))
                self._check_interaction(status, text, calls)
                interaction_id = str(_value(interaction, "id", ""))
                if not interaction_id:
                    raise ChatServiceError(
                        "INVALID_PROVIDER_RESPONSE",
                        "Falha temporaria ao gerar a resposta.",
                        502,
                    )
                if calls:
                    if tool_rounds >= self.settings.max_tool_rounds:
                        raise ChatServiceError(
                            "TOOL_ROUND_LIMIT",
                            "A consulta exigiu etapas demais. Reformule a pergunta.",
                            422,
                        )
                    current_input = await self._execute_calls(calls, correlation_id)
                    previous_id = interaction_id
                    tool_rounds += 1
                    continue
                await self.sessions.commit(session, interaction_id)
                logger.info(
                    "chat_turn_completed",
                    extra={
                        "correlation_id": correlation_id,
                        "model": self.settings.model,
                        "status": "completed",
                        "duration_ms": round((time.perf_counter() - started) * 1000),
                        "total_tokens": usage.total_tokens,
                    },
                )
                return ChatResponse(
                    conversation_id=session.conversation_id,
                    message=text,
                    model=self.settings.model,
                    usage=usage,
                )

    async def _stream_round(
        self,
        request: dict[str, Any],
        visible: list[bool],
    ) -> AsyncIterator[tuple[str, Any]]:
        assert self.gateway is not None
        for attempt in range(3):
            active_steps: dict[int, str] = {}
            calls: dict[int, dict[str, Any]] = {}
            interaction_id: str | None = None
            status: str | None = None
            usage = TokenUsage()
            try:
                iterator = self.gateway.stream(**request).__aiter__()
                deadline = asyncio.get_running_loop().time() + self.settings.timeout_seconds
                while True:
                    remaining = deadline - asyncio.get_running_loop().time()
                    if remaining <= 0:
                        raise asyncio.TimeoutError
                    try:
                        event = await asyncio.wait_for(anext(iterator), timeout=remaining)
                    except StopAsyncIteration:
                        break
                    event_type = _value(event, "event_type", "")
                    if event_type == "interaction.created":
                        interaction = _value(event, "interaction")
                        interaction_id = str(_value(interaction, "id", "")) or interaction_id
                    elif event_type == "step.start":
                        index = int(_value(event, "index", -1))
                        step = _value(event, "step")
                        step_type = str(_value(step, "type", ""))
                        active_steps[index] = step_type
                        if step_type == "function_call":
                            calls[index] = {
                                "name": str(_value(step, "name", "")),
                                "call_id": str(_value(step, "id", "")),
                                "arguments_raw": "",
                                "arguments": _value(step, "arguments", {}) or {},
                            }
                    elif event_type == "step.delta":
                        index = int(_value(event, "index", -1))
                        delta = _value(event, "delta")
                        delta_type = _value(delta, "type")
                        if delta_type == "text" and active_steps.get(index) == "model_output":
                            text = str(_value(delta, "text", ""))
                            if text:
                                visible[0] = True
                                yield "delta", text
                        elif delta_type == "arguments_delta" and index in calls:
                            calls[index]["arguments_raw"] += str(
                                _value(delta, "arguments", "")
                            )
                    elif event_type == "interaction.completed":
                        interaction = _value(event, "interaction")
                        interaction_id = str(_value(interaction, "id", "")) or interaction_id
                        status = _value(interaction, "status")
                        usage = _usage(_value(interaction, "usage"))
                    elif event_type == "error":
                        raw_error = _value(event, "error")
                        code = str(_value(raw_error, "code", "")).lower()
                        if "timeout" in code:
                            raise asyncio.TimeoutError
                        raise ChatServiceError(
                            "PROVIDER_ERROR",
                            "Falha temporaria ao gerar a resposta.",
                            502,
                        )
                assembled_calls = []
                for call in calls.values():
                    if call["arguments_raw"]:
                        try:
                            call["arguments"] = json.loads(call["arguments_raw"])
                        except json.JSONDecodeError as exc:
                            raise ChatServiceError(
                                "INVALID_TOOL_ARGUMENTS",
                                "A consulta produziu argumentos invalidos.",
                                502,
                            ) from exc
                    assembled_calls.append(
                        {
                            "name": call["name"],
                            "call_id": call["call_id"],
                            "arguments": call["arguments"],
                        }
                    )
                yield "complete", {
                    "interaction_id": interaction_id,
                    "status": status,
                    "usage": usage,
                    "calls": assembled_calls,
                }
                return
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                error = _provider_error(exc)
                if visible[0] or not error.retryable or attempt == 2:
                    raise error from exc
                await self._retry_delay(attempt, _retry_after_seconds(exc))

    async def stream_chat(
        self,
        message: str,
        session: ChatSession,
    ) -> AsyncIterator[StreamEvent]:
        self.ensure_configured()
        clean = self.validate_message(message)
        correlation_id = uuid.uuid4().hex
        started = time.perf_counter()
        usage = TokenUsage()
        visible = [False]
        yield StreamEvent(
            event="session",
            data={"conversation_id": session.conversation_id},
        )
        async with session.turn_lock:
            current_input: Any = clean
            previous_id = session.previous_interaction_id
            tool_rounds = 0
            while True:
                completion: dict[str, Any] | None = None
                async for kind, payload in self._stream_round(
                    self._request(current_input, previous_id),
                    visible,
                ):
                    if kind == "delta":
                        yield StreamEvent(event="delta", data={"text": payload})
                    else:
                        completion = payload
                if completion is None or not completion["interaction_id"]:
                    raise ChatServiceError(
                        "INVALID_PROVIDER_RESPONSE",
                        "Falha temporaria ao gerar a resposta.",
                        502,
                    )
                calls = completion["calls"]
                status = completion["status"]
                if status in {"blocked", "rejected", "safety_blocked"}:
                    raise ChatServiceError(
                        "CONTENT_BLOCKED",
                        "A solicitacao foi bloqueada pelos filtros de seguranca.",
                        422,
                    )
                usage = usage.add(completion["usage"])
                if calls:
                    if tool_rounds >= self.settings.max_tool_rounds:
                        raise ChatServiceError(
                            "TOOL_ROUND_LIMIT",
                            "A consulta exigiu etapas demais. Reformule a pergunta.",
                            422,
                        )
                    for call in calls:
                        yield StreamEvent(
                            event="status",
                            data={
                                "stage": "consulting_data",
                                "tool": call["name"],
                            },
                        )
                    current_input = await self._execute_calls(calls, correlation_id)
                    previous_id = completion["interaction_id"]
                    tool_rounds += 1
                    continue
                if not visible[0]:
                    raise ChatServiceError(
                        "EMPTY_PROVIDER_RESPONSE",
                        "Nao foi possivel gerar uma resposta segura.",
                        502,
                    )
                await self.sessions.commit(session, completion["interaction_id"])
                logger.info(
                    "chat_stream_completed",
                    extra={
                        "correlation_id": correlation_id,
                        "model": self.settings.model,
                        "status": "completed",
                        "duration_ms": round((time.perf_counter() - started) * 1000),
                        "total_tokens": usage.total_tokens,
                    },
                )
                yield StreamEvent(
                    event="done",
                    data={
                        "model": self.settings.model,
                        "usage": usage.model_dump(),
                    },
                )
                return
