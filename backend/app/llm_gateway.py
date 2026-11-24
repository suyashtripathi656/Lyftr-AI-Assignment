"""LLM gateway — explicit key-pool loop with LiteLLM for provider calls and caching.

Why an explicit loop instead of litellm.Router?
 - Exact control over key_id, fallback_attempts and the simulation hook.
 - LiteLLM still handles provider calls, retries=0 per key, and disk caching.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from typing import Any

import litellm
from litellm import Cache
from litellm.exceptions import (
    AuthenticationError,
    RateLimitError,
    ServiceUnavailableError,
    InternalServerError,
    Timeout,
    APIConnectionError,
)

from . import config

logger = logging.getLogger("llm_gateway")

# ---------------------------------------------------------------------------
# Cache setup
# ---------------------------------------------------------------------------

_cache_enabled = False


def setup_cache() -> None:
    """Initialise LiteLLM local disk cache."""
    global _cache_enabled
    os.makedirs(config.settings.cache_dir, exist_ok=True)
    litellm.cache = Cache(type="local")  # local = in-process diskcache
    _cache_enabled = True
    logger.info("LiteLLM local cache enabled at %s", config.settings.cache_dir)


def is_cache_enabled() -> bool:
    return _cache_enabled


# ---------------------------------------------------------------------------
# Failure simulation
# ---------------------------------------------------------------------------

_SIMULATED_STATUS_CODES = {429, 500, 502, 503}


def _parse_simulation_header(header: str) -> dict[str, int]:
    """Parse e.g. 'key_1=429,key_2=500' or '*=429'. Lenient: skip bad pairs."""
    result: dict[str, int] = {}
    for part in header.split(","):
        part = part.strip()
        if "=" not in part:
            continue
        try:
            k, v = part.split("=", 1)
            k = k.strip()
            code = int(v.strip())
            if code in _SIMULATED_STATUS_CODES:
                result[k] = code
        except (ValueError, TypeError):
            continue
    return result


def _raise_simulated(status_code: int, key_id: str) -> None:
    """Raise the LiteLLM exception matching the simulated status code."""
    msg = f"Simulated {status_code} for {key_id}"
    if status_code == 429:
        raise RateLimitError(message=msg, llm_provider="simulated", model="simulated", response=None)
    elif status_code == 500:
        raise InternalServerError(message=msg, llm_provider="simulated", model="simulated", response=None)
    elif status_code == 502:
        raise InternalServerError(message=msg, llm_provider="simulated", model="simulated", response=None)
    elif status_code == 503:
        raise ServiceUnavailableError(message=msg, llm_provider="simulated", model="simulated", response=None)


# ---------------------------------------------------------------------------
# Custom cache key
# ---------------------------------------------------------------------------

def _cache_key(model: str, messages: list[dict[str, str]]) -> str:
    """Deterministic cache key = sha256(model + canonical JSON of messages).

    Excludes api_key so a hit works regardless of which key answered.
    """
    payload = json.dumps({"model": model, "messages": messages}, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(payload.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Completion with failover
# ---------------------------------------------------------------------------

_FAILOVER_EXCEPTIONS = (
    RateLimitError,
    InternalServerError,
    ServiceUnavailableError,
    Timeout,
    APIConnectionError,
    AuthenticationError,
)


async def complete(
    messages: list[dict[str, str]],
    *,
    simulation_header: str | None = None,
) -> dict[str, Any]:
    """Call LiteLLM with an explicit key-pool loop.

    Returns a dict ready to become ChatResponse.metadata plus a "reply" key.
    """
    model = config.settings.llm_model
    keys = config.settings.api_keys
    key_ids = config.settings.key_ids

    # Parse simulation overrides (only when feature is enabled)
    sim_map: dict[str, int] = {}
    bypass_cache_read = False
    if config.settings.enable_failure_simulation and simulation_header:
        sim_map = _parse_simulation_header(simulation_header)
        bypass_cache_read = True  # bypass cache READ so tests are deterministic

    cache_key = _cache_key(model, messages)
    fallback_attempts = 0
    last_exc: Exception | None = None

    start = time.perf_counter()

    for idx, api_key in enumerate(keys):
        kid = key_ids[api_key]

        # --- simulation hook (before calling provider) ---
        sim_code = sim_map.get(kid) or sim_map.get("*")
        if sim_code:
            logger.info("Simulating %d for %s", sim_code, kid)
            fallback_attempts += 1
            last_exc = None
            try:
                _raise_simulated(sim_code, kid)
            except _FAILOVER_EXCEPTIONS as exc:
                last_exc = exc
                continue

        try:
            kwargs: dict[str, Any] = {
                "model": model,
                "messages": messages,
                "api_key": api_key,
                "num_retries": 0,
                "timeout": 20,
                "temperature": 0,
                "caching": not bypass_cache_read,  # disable cache reads during simulation
                "cache_key": cache_key,
            }
            response = await litellm.acompletion(**kwargs)

            # Detect cache hit
            cache_hit = False
            hidden = getattr(response, "_hidden_params", {})
            if hidden and hidden.get("cache_hit") is True:
                cache_hit = True

            # Extract reply text
            reply_text = ""
            if response.choices and response.choices[0].message:
                reply_text = response.choices[0].message.content or ""
            reply_text = reply_text.strip()

            # Empty reply → treat as failed key
            if not reply_text:
                fallback_attempts += 1
                last_exc = Exception("Empty reply from model")
                continue

            # Extract token usage
            usage = getattr(response, "usage", None)
            input_tokens = 0
            output_tokens = 0
            if usage:
                input_tokens = getattr(usage, "prompt_tokens", 0) or 0
                output_tokens = getattr(usage, "completion_tokens", 0) or 0
            else:
                # Fallback to litellm.token_counter
                try:
                    input_tokens = litellm.token_counter(model=model, messages=messages)
                except Exception:
                    pass
                try:
                    output_tokens = litellm.token_counter(model=model, text=reply_text)
                except Exception:
                    pass

            elapsed_ms = int((time.perf_counter() - start) * 1000)

            return {
                "reply": reply_text,
                "resolution_source": "LLM_CACHE" if cache_hit else "LIVE_INFERENCE",
                "model": model,
                "latency_ms": elapsed_ms,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "key_id": None if cache_hit else kid,
                "fallback_attempts": 0 if cache_hit else fallback_attempts,
            }

        except _FAILOVER_EXCEPTIONS as exc:
            logger.warning("Key %s failed: %s", kid, exc)
            fallback_attempts += 1
            last_exc = exc
            continue

    # All keys exhausted
    elapsed_ms = int((time.perf_counter() - start) * 1000)
    logger.error("All %d keys failed. Last error: %s", len(keys), last_exc)
    raise AllProvidersUnavailableError(f"all providers unavailable (last: {last_exc})")


class AllProvidersUnavailableError(Exception):
    """Raised when every key in the pool has been exhausted."""
    pass
