"""Armazenamento desacoplado de sessoes conversacionais."""

from __future__ import annotations

import asyncio
import re
import secrets
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Protocol

_CONVERSATION_ID_RE = re.compile(r"^[A-Za-z0-9_-]{32,128}$")


class SessionNotFoundError(LookupError):
    """Conversa desconhecida, expirada ou malformada."""


@dataclass
class ChatSession:
    conversation_id: str
    previous_interaction_id: str | None
    expires_at: float
    last_access: float
    turn_lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class SessionStore(Protocol):
    async def create(self) -> ChatSession: ...

    async def get(self, conversation_id: str) -> ChatSession: ...

    async def commit(self, session: ChatSession, interaction_id: str) -> None: ...

    async def delete(self, conversation_id: str) -> None: ...


class InMemorySessionStore:
    """Store local com TTL, LRU, limite e lock por conversa."""

    def __init__(
        self,
        ttl_seconds: int,
        max_sessions: int,
        clock=time.monotonic,
    ) -> None:
        if ttl_seconds <= 0 or max_sessions <= 0:
            raise ValueError("TTL e limite de sessoes devem ser positivos")
        self._ttl = ttl_seconds
        self._max_sessions = max_sessions
        self._clock = clock
        self._sessions: OrderedDict[str, ChatSession] = OrderedDict()
        self._lock = asyncio.Lock()

    def _purge_expired(self, now: float) -> None:
        expired = [
            key for key, value in self._sessions.items() if value.expires_at <= now
        ]
        for key in expired:
            self._sessions.pop(key, None)

    async def create(self) -> ChatSession:
        async with self._lock:
            now = self._clock()
            self._purge_expired(now)
            while len(self._sessions) >= self._max_sessions:
                self._sessions.popitem(last=False)
            conversation_id = secrets.token_urlsafe(32)
            session = ChatSession(
                conversation_id=conversation_id,
                previous_interaction_id=None,
                expires_at=now + self._ttl,
                last_access=now,
            )
            self._sessions[conversation_id] = session
            return session

    async def get(self, conversation_id: str) -> ChatSession:
        if not _CONVERSATION_ID_RE.fullmatch(conversation_id):
            raise SessionNotFoundError("Conversa invalida")
        async with self._lock:
            now = self._clock()
            self._purge_expired(now)
            session = self._sessions.get(conversation_id)
            if session is None:
                raise SessionNotFoundError("Conversa ausente ou expirada")
            session.last_access = now
            session.expires_at = now + self._ttl
            self._sessions.move_to_end(conversation_id)
            return session

    async def commit(self, session: ChatSession, interaction_id: str) -> None:
        async with self._lock:
            current = self._sessions.get(session.conversation_id)
            if current is not session:
                raise SessionNotFoundError("Conversa ausente ou expirada")
            now = self._clock()
            session.previous_interaction_id = interaction_id
            session.last_access = now
            session.expires_at = now + self._ttl
            self._sessions.move_to_end(session.conversation_id)

    async def delete(self, conversation_id: str) -> None:
        if not _CONVERSATION_ID_RE.fullmatch(conversation_id):
            return
        async with self._lock:
            self._sessions.pop(conversation_id, None)
