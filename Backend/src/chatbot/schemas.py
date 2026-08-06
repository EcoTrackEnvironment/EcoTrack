"""Contratos HTTP e tipos internos do chatbot."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(..., min_length=1)
    conversation_id: str | None = Field(default=None, max_length=128)


class TokenUsage(BaseModel):
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None

    def add(self, other: "TokenUsage") -> "TokenUsage":
        def total(a: int | None, b: int | None) -> int | None:
            return None if a is None and b is None else (a or 0) + (b or 0)

        return TokenUsage(
            input_tokens=total(self.input_tokens, other.input_tokens),
            output_tokens=total(self.output_tokens, other.output_tokens),
            total_tokens=total(self.total_tokens, other.total_tokens),
        )


class ChatResponse(BaseModel):
    conversation_id: str
    message: str
    model: str
    usage: TokenUsage


class ConversationDeleteResponse(BaseModel):
    conversation_id: str
    cleared: bool = True
    remote_deleted: bool = False


class StreamEvent(BaseModel):
    event: Literal["session", "status", "delta", "done", "error"]
    data: dict[str, Any]
