"""Pydantic models for request / response validation."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=128)
    message: str
    system_prompt: str | None = None

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("message must not be empty or whitespace-only")
        if len(trimmed) > 4000:
            raise ValueError("message must be at most 4000 characters")
        return trimmed


class MetadataResponse(BaseModel):
    resolution_source: str
    model: str
    latency_ms: int
    input_tokens: int
    output_tokens: int
    key_id: str | None
    fallback_attempts: int


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    metadata: MetadataResponse


class HealthResponse(BaseModel):
    status: str
    keys_configured: int
    cache_enabled: bool


class MessageOut(BaseModel):
    role: str
    content: str
    metadata: dict | None = None


class MessagesResponse(BaseModel):
    session_id: str
    messages: list[MessageOut]
