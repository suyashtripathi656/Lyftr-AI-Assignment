#!/usr/bin/env python3
"""Cross-platform smoke test for the LLM Chatbot API contract."""

import json
import sys
import time
import urllib.error
import urllib.request

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
PASS = 0
FAIL = 0


def log_pass(desc: str) -> None:
    global PASS
    PASS += 1
    print(f"\033[32m✓ PASS\033[0m {desc}")


def log_fail(desc: str) -> None:
    global FAIL
    FAIL += 1
    print(f"\033[31m✗ FAIL\033[0m {desc}")


def http_req(
    path: str,
    method: str = "GET",
    body: dict | None = None,
    headers: dict | None = None,
    raw_data: str | None = None,
):
    url = f"{BASE_URL}{path}"
    hdrs = dict(headers or {})
    data = None

    if body is not None:
        hdrs["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    elif raw_data is not None:
        hdrs["Content-Type"] = "application/json"
        data = raw_data.encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            raw = resp.read().decode("utf-8")
            parsed = json.loads(raw) if raw else None
            return resp.status, parsed
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        parsed = json.loads(raw) if raw else None
        return e.code, parsed
    except Exception as e:
        return 0, str(e)


print(f"===== Smoke Test: {BASE_URL} =====\n")

# 1. Health
print("--- Health ---")
status, data = http_req("/health")
if status == 200:
    log_pass("GET /health -> 200")
else:
    log_fail(f"GET /health -> 200 (got {status})")

if (
    isinstance(data, dict)
    and data.get("status") == "ok"
    and data.get("keys_configured", 0) >= 2
    and data.get("cache_enabled") is True
):
    log_pass("Health body shape")
else:
    log_fail(f"Health body shape (got {data})")

# 2. Validation
print("\n--- Validation (422) ---")
s, d = http_req("/chat", "POST", body={"session_id": "v1", "message": ""})
if s == 422 and "detail" in (d or {}):
    log_pass("Empty message -> 422 JSON")
else:
    log_fail(f"Empty message -> 422 JSON (got {s}, {d})")

s, d = http_req("/chat", "POST", body={"session_id": "v2", "message": "   \n\t  "})
if s == 422 and "detail" in (d or {}):
    log_pass("Whitespace-only -> 422 JSON")
else:
    log_fail(f"Whitespace-only -> 422 JSON (got {s}, {d})")

s, d = http_req("/chat", "POST", body={"message": "missing session id"})
if s == 422 and "detail" in (d or {}):
    log_pass("Missing session_id -> 422 JSON")
else:
    log_fail(f"Missing session_id -> 422 JSON (got {s}, {d})")

s, d = http_req("/chat", "POST", raw_data="not json")
if s == 422 and "detail" in (d or {}):
    log_pass("Malformed JSON -> 422 JSON")
else:
    log_fail(f"Malformed JSON -> 422 JSON (got {s}, {d})")

# 3. Failover & Simulation
print("\n--- Failover Simulation ---")
s, d = http_req(
    "/chat",
    "POST",
    body={"session_id": f"fo-429-{int(time.time())}", "message": "hello"},
    headers={"X-Simulate-Failure": "key_1=429"},
)
if s == 200 and d and d.get("metadata", {}).get("key_id") == "key_2":
    log_pass("key_1=429 -> key_2 answers")
else:
    log_fail(f"key_1=429 -> key_2 answers (got {s}, {d})")

s, d = http_req(
    "/chat",
    "POST",
    body={"session_id": f"fo-500-{int(time.time())}", "message": "hello"},
    headers={"X-Simulate-Failure": "key_1=500"},
)
if s == 200 and d and d.get("metadata", {}).get("key_id") == "key_2":
    log_pass("key_1=500 -> key_2 answers")
else:
    log_fail(f"key_1=500 -> key_2 answers (got {s}, {d})")

s, d = http_req(
    "/chat",
    "POST",
    body={"session_id": f"fo-all-{int(time.time())}", "message": "hello"},
    headers={"X-Simulate-Failure": "*=429"},
)
if s == 503 and d and d.get("detail") == "all providers unavailable":
    log_pass("*=429 -> 503 all providers unavailable")
else:
    log_fail(f"*=429 -> 503 (got {s}, {d})")

# 4. History 404
print("\n--- History 404 ---")
s, d = http_req("/sessions/nonexistent-session-xyz/messages")
if s == 404 and d and d.get("detail") == "session not found":
    log_pass("Unknown session -> 404 JSON")
else:
    log_fail(f"Unknown session -> 404 (got {s}, {d})")

print(f"\n=====================================")
print(f"  PASS: {PASS}   FAIL: {FAIL}")
print(f"=====================================")
sys.exit(0 if FAIL == 0 else 1)
