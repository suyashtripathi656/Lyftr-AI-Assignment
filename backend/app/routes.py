"""API route handlers."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from . import config, db
from .llm_gateway import AllProvidersUnavailableError, complete, is_cache_enabled
from .schemas import (
    ChatRequest,
    ChatResponse,
    HealthResponse,
    MessagesResponse,
    MetadataResponse,
)

logger = logging.getLogger("routes")

router = APIRouter()


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------

@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse | JSONResponse:
    if not db.check_db():
        return JSONResponse(
            status_code=503,
            content={"detail": "database unreachable"},
        )
    if not config.settings.api_keys:
        return JSONResponse(
            status_code=503,
            content={"detail": "no API keys configured"},
        )
    return HealthResponse(
        status="ok",
        keys_configured=len(config.settings.api_keys),
        cache_enabled=is_cache_enabled(),
    )


# ---------------------------------------------------------------------------
# POST /chat
# ---------------------------------------------------------------------------

@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    x_simulate_failure: str | None = Header(None, alias="X-Simulate-Failure"),
) -> ChatResponse | JSONResponse:
    session_id = body.session_id
    user_message = body.message  # already trimmed by the validator

    # --- Session handling ---
    session = db.get_session(session_id)
    if session is None:
        system_prompt = body.system_prompt or config.settings.default_system_prompt
        db.create_session(session_id, system_prompt)
    else:
        if body.system_prompt is not None:
            db.update_session_system_prompt(session_id, body.system_prompt)

    # Resolve effective system prompt
    session = db.get_session(session_id)
    system_prompt = session["system_prompt"] or config.settings.default_system_prompt

    # --- Build LLM messages ---
    llm_messages = db.get_history_for_llm(
        session_id, system_prompt, config.settings.max_history_messages
    )
    llm_messages.append({"role": "user", "content": user_message})

    # --- Call LLM ---
    try:
        result = await complete(
            llm_messages,
            simulation_header=x_simulate_failure,
        )
    except AllProvidersUnavailableError:
        return JSONResponse(
            status_code=503,
            content={"detail": "all providers unavailable"},
        )

    # --- Persist (single transaction, only on success) ---
    metadata: dict[str, Any] = {
        "resolution_source": result["resolution_source"],
        "model": result["model"],
        "latency_ms": result["latency_ms"],
        "input_tokens": result["input_tokens"],
        "output_tokens": result["output_tokens"],
        "key_id": result["key_id"],
        "fallback_attempts": result["fallback_attempts"],
    }
    db.save_exchange(session_id, user_message, result["reply"], metadata)

    return ChatResponse(
        session_id=session_id,
        reply=result["reply"],
        metadata=MetadataResponse(**metadata),
    )


# ---------------------------------------------------------------------------
# GET /sessions/{session_id}/messages
# ---------------------------------------------------------------------------

@router.get("/sessions/{session_id}/messages", response_model=MessagesResponse)
async def get_messages(session_id: str) -> MessagesResponse | JSONResponse:
    session = db.get_session(session_id)
    if session is None:
        return JSONResponse(status_code=404, content={"detail": "session not found"})

    msgs = db.get_messages(session_id)
    return MessagesResponse(session_id=session_id, messages=msgs)
