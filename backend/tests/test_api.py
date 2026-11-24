"""Comprehensive backend test suite — no network, all LLM calls mocked."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helper: mock litellm.acompletion
# ---------------------------------------------------------------------------

def _make_response(content: str = "Hello!", input_tokens: int = 10, output_tokens: int = 5, cache_hit: bool = False):
    """Build a mock LiteLLM ModelResponse."""
    msg = MagicMock()
    msg.content = content

    choice = MagicMock()
    choice.message = msg

    usage = MagicMock()
    usage.prompt_tokens = input_tokens
    usage.completion_tokens = output_tokens

    resp = MagicMock()
    resp.choices = [choice]
    resp.usage = usage
    resp._hidden_params = {"cache_hit": cache_hit}
    return resp


def _mock_acompletion(**overrides):
    """Return an AsyncMock that returns a standard response."""
    resp = _make_response(**overrides)
    return AsyncMock(return_value=resp)


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------

class TestHealth:
    def test_health_ok(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["keys_configured"] == 2
        assert body["cache_enabled"] is True


# ---------------------------------------------------------------------------
# Validation (422)
# ---------------------------------------------------------------------------

class TestValidation:
    def test_missing_session_id(self, client):
        r = client.post("/chat", json={"message": "hi"})
        assert r.status_code == 422
        assert "detail" in r.json()

    def test_empty_message(self, client):
        r = client.post("/chat", json={"session_id": "s1", "message": ""})
        assert r.status_code == 422

    def test_whitespace_only_message(self, client):
        r = client.post("/chat", json={"session_id": "s1", "message": "   \n\t  "})
        assert r.status_code == 422

    def test_message_too_long(self, client):
        r = client.post("/chat", json={"session_id": "s1", "message": "x" * 4001})
        assert r.status_code == 422

    def test_malformed_json(self, client):
        r = client.post("/chat", content=b"not json", headers={"Content-Type": "application/json"})
        assert r.status_code == 422
        body = r.json()
        assert "detail" in body


# ---------------------------------------------------------------------------
# Multi-turn memory
# ---------------------------------------------------------------------------

class TestMultiTurn:
    @patch("litellm.acompletion")
    def test_history_passed_on_turn_2(self, mock_llm, client):
        mock_llm.side_effect = [
            _make_response("Reply 1"),
            _make_response("Reply 2"),
        ]

        # Turn 1
        r1 = client.post("/chat", json={"session_id": "mem1", "message": "Hello"})
        assert r1.status_code == 200

        # Turn 2
        r2 = client.post("/chat", json={"session_id": "mem1", "message": "Follow up"})
        assert r2.status_code == 200

        # The second call should include history
        second_call_messages = mock_llm.call_args_list[1].kwargs.get("messages") or mock_llm.call_args_list[1][1].get("messages")
        # Should have: system, user(Hello), assistant(Reply 1), user(Follow up)
        assert len(second_call_messages) >= 4
        roles = [m["role"] for m in second_call_messages]
        assert roles[0] == "system"
        assert "user" in roles
        assert "assistant" in roles


# ---------------------------------------------------------------------------
# Session isolation
# ---------------------------------------------------------------------------

class TestSessionIsolation:
    @patch("litellm.acompletion")
    def test_sessions_are_isolated(self, mock_llm, client):
        mock_llm.return_value = _make_response("I am isolated")

        # Session A
        client.post("/chat", json={"session_id": "iso-a", "message": "Session A message"})
        # Session B
        client.post("/chat", json={"session_id": "iso-b", "message": "Session B message"})

        # Check history
        ra = client.get("/sessions/iso-a/messages")
        rb = client.get("/sessions/iso-b/messages")
        assert ra.status_code == 200
        assert rb.status_code == 200
        msgs_a = ra.json()["messages"]
        msgs_b = rb.json()["messages"]
        assert len(msgs_a) == 2  # user + assistant
        assert len(msgs_b) == 2
        assert msgs_a[0]["content"] == "Session A message"
        assert msgs_b[0]["content"] == "Session B message"


# ---------------------------------------------------------------------------
# History endpoint
# ---------------------------------------------------------------------------

class TestHistory:
    @patch("litellm.acompletion")
    def test_history_shape(self, mock_llm, client):
        mock_llm.return_value = _make_response("world")

        client.post("/chat", json={"session_id": "hist1", "message": "hello"})
        r = client.get("/sessions/hist1/messages")
        assert r.status_code == 200
        body = r.json()
        assert body["session_id"] == "hist1"
        msgs = body["messages"]
        assert len(msgs) == 2
        assert msgs[0]["role"] == "user"
        assert msgs[0]["content"] == "hello"
        assert msgs[1]["role"] == "assistant"
        assert msgs[1]["content"] == "world"
        # Assistant has metadata
        assert "metadata" in msgs[1]
        meta = msgs[1]["metadata"]
        assert "resolution_source" in meta
        assert "input_tokens" in meta
        assert "output_tokens" in meta

    def test_history_404(self, client):
        r = client.get("/sessions/nonexistent/messages")
        assert r.status_code == 404
        assert r.json()["detail"] == "session not found"


# ---------------------------------------------------------------------------
# Cache hit
# ---------------------------------------------------------------------------

class TestCacheHit:
    @patch("litellm.acompletion")
    def test_cache_hit_on_identical_first_message(self, mock_llm, client):
        resp_live = _make_response("cached reply", cache_hit=False)
        resp_cached = _make_response("cached reply", cache_hit=True)
        mock_llm.side_effect = [resp_live, resp_cached]

        # First call — LIVE
        r1 = client.post("/chat", json={"session_id": "cache-a", "message": "What is 2+2?"})
        assert r1.status_code == 200
        m1 = r1.json()["metadata"]
        assert m1["resolution_source"] == "LIVE_INFERENCE"

        # Second call — different session, same message → CACHE
        r2 = client.post("/chat", json={"session_id": "cache-b", "message": "What is 2+2?"})
        assert r2.status_code == 200
        m2 = r2.json()["metadata"]
        assert m2["resolution_source"] == "LLM_CACHE"
        assert m2["key_id"] is None
        assert r2.json()["reply"] == "cached reply"

    @patch("litellm.acompletion")
    def test_different_message_no_cache(self, mock_llm, client):
        mock_llm.side_effect = [
            _make_response("reply a"),
            _make_response("reply b"),
        ]

        client.post("/chat", json={"session_id": "nc-a", "message": "What is 2+2?"})
        r2 = client.post("/chat", json={"session_id": "nc-b", "message": "What is 3+3?"})
        m2 = r2.json()["metadata"]
        assert m2["resolution_source"] == "LIVE_INFERENCE"


# ---------------------------------------------------------------------------
# Per-request tokens (not cumulative)
# ---------------------------------------------------------------------------

class TestTokens:
    @patch("litellm.acompletion")
    def test_tokens_per_request(self, mock_llm, client):
        mock_llm.side_effect = [
            _make_response("r1", input_tokens=15, output_tokens=8),
            _make_response("r2", input_tokens=25, output_tokens=12),
        ]

        r1 = client.post("/chat", json={"session_id": "tok1", "message": "one"})
        r2 = client.post("/chat", json={"session_id": "tok1", "message": "two"})

        m1 = r1.json()["metadata"]
        m2 = r2.json()["metadata"]

        # Tokens must be per-request, not cumulative
        assert m1["input_tokens"] == 15
        assert m1["output_tokens"] == 8
        assert m2["input_tokens"] == 25
        assert m2["output_tokens"] == 12


# ---------------------------------------------------------------------------
# Failover
# ---------------------------------------------------------------------------

class TestFailover:
    @patch("litellm.acompletion")
    def test_key1_429_falls_to_key2(self, mock_llm, client):
        mock_llm.return_value = _make_response("from key 2")

        r = client.post(
            "/chat",
            json={"session_id": "fo1", "message": "hi"},
            headers={"X-Simulate-Failure": "key_1=429"},
        )
        assert r.status_code == 200
        meta = r.json()["metadata"]
        assert meta["key_id"] == "key_2"
        assert meta["fallback_attempts"] == 1
        assert meta["resolution_source"] == "LIVE_INFERENCE"

    @patch("litellm.acompletion")
    def test_key1_500_falls_to_key2(self, mock_llm, client):
        mock_llm.return_value = _make_response("from key 2")

        r = client.post(
            "/chat",
            json={"session_id": "fo2", "message": "hi"},
            headers={"X-Simulate-Failure": "key_1=500"},
        )
        assert r.status_code == 200
        meta = r.json()["metadata"]
        assert meta["key_id"] == "key_2"
        assert meta["fallback_attempts"] == 1

    @patch("litellm.acompletion")
    def test_all_keys_fail_503(self, mock_llm, client):
        r = client.post(
            "/chat",
            json={"session_id": "fo3", "message": "hi"},
            headers={"X-Simulate-Failure": "*=429"},
        )
        assert r.status_code == 503
        assert r.json()["detail"] == "all providers unavailable"

        # Nothing persisted
        rh = client.get("/sessions/fo3/messages")
        # Either 404 or empty messages
        if rh.status_code == 200:
            assert len(rh.json()["messages"]) == 0
        else:
            assert rh.status_code == 404

    @patch("litellm.acompletion")
    def test_simulation_ignored_when_disabled(self, mock_llm, client, monkeypatch):
        """When ENABLE_FAILURE_SIMULATION=false, the header is ignored."""
        from backend.app import config as cfg_mod
        monkeypatch.setattr(cfg_mod.settings, "enable_failure_simulation", False)

        mock_llm.return_value = _make_response("from key 1")

        r = client.post(
            "/chat",
            json={"session_id": "sim-off", "message": "hi"},
            headers={"X-Simulate-Failure": "key_1=429"},
        )
        assert r.status_code == 200
        # key_1 should answer (simulation not applied)
        assert r.json()["metadata"]["key_id"] == "key_1"

    @patch("litellm.acompletion")
    def test_real_exception_failover(self, mock_llm, client, monkeypatch):
        """Real LiteLLM exception on key_1 → failover to key_2."""
        from backend.app import config as cfg_mod
        monkeypatch.setattr(cfg_mod.settings, "enable_failure_simulation", False)

        from litellm.exceptions import RateLimitError

        mock_llm.side_effect = [
            RateLimitError(message="rate limited", llm_provider="test", model="test", response=None),
            _make_response("from key 2"),
        ]

        r = client.post(
            "/chat",
            json={"session_id": "real-fo", "message": "hi"},
        )
        assert r.status_code == 200
        assert r.json()["metadata"]["key_id"] == "key_2"
        assert r.json()["metadata"]["fallback_attempts"] == 1


# ---------------------------------------------------------------------------
# No key leakage
# ---------------------------------------------------------------------------

class TestNoKeyLeakage:
    @patch("litellm.acompletion")
    def test_no_keys_in_response(self, mock_llm, client):
        mock_llm.return_value = _make_response("safe reply")

        r = client.post("/chat", json={"session_id": "leak1", "message": "hi"})
        body_str = r.text
        assert "test-key-aaa" not in body_str
        assert "test-key-bbb" not in body_str

        rh = client.get("/sessions/leak1/messages")
        body_str = rh.text
        assert "test-key-aaa" not in body_str
        assert "test-key-bbb" not in body_str


# ---------------------------------------------------------------------------
# Error response format
# ---------------------------------------------------------------------------

class TestErrorFormat:
    def test_422_is_json(self, client):
        r = client.post("/chat", json={"session_id": "s1", "message": ""})
        assert r.headers["content-type"].startswith("application/json")
        assert "detail" in r.json()

    def test_404_is_json(self, client):
        r = client.get("/sessions/nope/messages")
        assert r.headers["content-type"].startswith("application/json")
        assert r.json()["detail"] == "session not found"
