#!/usr/bin/env bash
# smoke_test.sh — Contract verification for the LLM Chatbot API
# Usage: ./scripts/smoke_test.sh <BACKEND_URL>
# Example: ./scripts/smoke_test.sh http://localhost:8000

set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"
PYTHON_BIN=$(command -v python3 2>/dev/null || command -v python 2>/dev/null || echo "python")
PASS=0
FAIL=0
SESSION_ID="smoke-$(date +%s)"

green() { printf "\033[32m✓ PASS\033[0m %s\n" "$1"; PASS=$((PASS + 1)); }
red()   { printf "\033[31m✗ FAIL\033[0m %s\n" "$1"; FAIL=$((FAIL + 1)); }
check() { if [ "$1" = "0" ]; then green "$2"; else red "$2"; fi; }

echo "===== Smoke Test: $BASE_URL ====="
echo ""

# --- 1. Health ---
echo "--- Health ---"
HEALTH=$(curl -s -w "\n%{http_code}" "$BASE_URL/health")
HTTP_CODE=$(echo "$HEALTH" | tail -1)
BODY=$(echo "$HEALTH" | sed '$d')
[ "$HTTP_CODE" = "200" ] && check 0 "GET /health → 200" || check 1 "GET /health → 200 (got $HTTP_CODE)"
echo "$BODY" | "$PYTHON_BIN" -c "import sys,json; d=json.load(sys.stdin); assert d['status']=='ok'; assert d['keys_configured']>=2; assert d['cache_enabled']==True" 2>/dev/null \
  && check 0 "Health body shape" || check 1 "Health body shape"

# --- 2. Chat (normal) ---
echo ""
echo "--- Chat ---"
CHAT1=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/chat" \
  -H "Content-Type: application/json" \
  -d "{\"session_id\":\"$SESSION_ID\",\"message\":\"What is 2+2? Reply with just the number.\"}")
HTTP_CODE=$(echo "$CHAT1" | tail -1)
BODY=$(echo "$CHAT1" | sed '$d')
[ "$HTTP_CODE" = "200" ] && check 0 "POST /chat → 200" || check 1 "POST /chat → 200 (got $HTTP_CODE)"
echo "$BODY" | "$PYTHON_BIN" -c "
import sys,json
d=json.load(sys.stdin)
assert 'reply' in d and len(d['reply'])>0
m=d['metadata']
assert m['resolution_source'] in ('LIVE_INFERENCE','LLM_CACHE')
assert isinstance(m['latency_ms'],int)
assert isinstance(m['input_tokens'],int)
assert isinstance(m['output_tokens'],int)
assert 'key_id' in m
assert 'fallback_attempts' in m
" 2>/dev/null && check 0 "Chat response shape" || check 1 "Chat response shape"

# --- 3. Cache hit ---
echo ""
echo "--- Cache ---"
SESSION_CACHE="cache-$(date +%s)"
curl -s -X POST "$BASE_URL/chat" \
  -H "Content-Type: application/json" \
  -d "{\"session_id\":\"$SESSION_CACHE-a\",\"message\":\"What is the capital of France?\"}" > /dev/null

CACHE_HIT=$(curl -s -X POST "$BASE_URL/chat" \
  -H "Content-Type: application/json" \
  -d "{\"session_id\":\"$SESSION_CACHE-b\",\"message\":\"What is the capital of France?\"}")
echo "$CACHE_HIT" | "$PYTHON_BIN" -c "
import sys,json; d=json.load(sys.stdin)
assert d['metadata']['resolution_source']=='LLM_CACHE'
assert d['metadata']['key_id'] is None
" 2>/dev/null && check 0 "Cache hit on identical first message" || check 1 "Cache hit on identical first message"

# Different message → no cache
CACHE_MISS=$(curl -s -X POST "$BASE_URL/chat" \
  -H "Content-Type: application/json" \
  -d "{\"session_id\":\"$SESSION_CACHE-c\",\"message\":\"What is the capital of Germany?\"}")
echo "$CACHE_MISS" | "$PYTHON_BIN" -c "
import sys,json; d=json.load(sys.stdin)
assert d['metadata']['resolution_source']=='LIVE_INFERENCE'
" 2>/dev/null && check 0 "Different message → LIVE_INFERENCE" || check 1 "Different message → LIVE_INFERENCE"

# --- 4. Failover (key_1=429) ---
echo ""
echo "--- Failover ---"
FO1=$(curl -s -X POST "$BASE_URL/chat" \
  -H "Content-Type: application/json" \
  -H "X-Simulate-Failure: key_1=429" \
  -d "{\"session_id\":\"fo-429-$(date +%s)\",\"message\":\"hello\"}")
echo "$FO1" | "$PYTHON_BIN" -c "
import sys,json; d=json.load(sys.stdin)
assert d['metadata']['key_id']=='key_2'
assert d['metadata']['fallback_attempts']==1
" 2>/dev/null && check 0 "key_1=429 → key_2 answers" || check 1 "key_1=429 → key_2 answers"

# key_1=500
FO2=$(curl -s -X POST "$BASE_URL/chat" \
  -H "Content-Type: application/json" \
  -H "X-Simulate-Failure: key_1=500" \
  -d "{\"session_id\":\"fo-500-$(date +%s)\",\"message\":\"hello\"}")
echo "$FO2" | "$PYTHON_BIN" -c "
import sys,json; d=json.load(sys.stdin)
assert d['metadata']['key_id']=='key_2'
assert d['metadata']['fallback_attempts']==1
" 2>/dev/null && check 0 "key_1=500 → key_2 answers" || check 1 "key_1=500 → key_2 answers"

# *=429 → 503
FO3=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/chat" \
  -H "Content-Type: application/json" \
  -H "X-Simulate-Failure: *=429" \
  -d "{\"session_id\":\"fo-all-$(date +%s)\",\"message\":\"hello\"}")
HTTP_CODE=$(echo "$FO3" | tail -1)
BODY=$(echo "$FO3" | sed '$d')
[ "$HTTP_CODE" = "503" ] && check 0 "*=429 → 503" || check 1 "*=429 → 503 (got $HTTP_CODE)"
echo "$BODY" | "$PYTHON_BIN" -c "import sys,json; d=json.load(sys.stdin); assert d['detail']=='all providers unavailable'" 2>/dev/null \
  && check 0 "503 detail message" || check 1 "503 detail message"

# --- 5. Per-message tokens ---
echo ""
echo "--- Tokens ---"
TOK_SESSION="tok-$(date +%s)"
TOK1=$(curl -s -X POST "$BASE_URL/chat" \
  -H "Content-Type: application/json" \
  -d "{\"session_id\":\"$TOK_SESSION\",\"message\":\"Say hello\"}")
TOK2=$(curl -s -X POST "$BASE_URL/chat" \
  -H "Content-Type: application/json" \
  -d "{\"session_id\":\"$TOK_SESSION\",\"message\":\"Now say goodbye\"}")
"$PYTHON_BIN" -c "
import json
t1=json.loads('$TOK1')['metadata']
t2=json.loads('$TOK2')['metadata']
# Tokens should be per-request (turn 2 may differ but should not be cumulative)
print(f'  Turn 1: in={t1[\"input_tokens\"]}, out={t1[\"output_tokens\"]}')
print(f'  Turn 2: in={t2[\"input_tokens\"]}, out={t2[\"output_tokens\"]}')
" 2>/dev/null && check 0 "Per-request tokens reported" || check 1 "Per-request tokens reported"

# --- 6. Validation (422) ---
echo ""
echo "--- Validation ---"
V1=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/chat" \
  -H "Content-Type: application/json" \
  -d "{\"session_id\":\"v1\",\"message\":\"\"}")
HTTP_CODE=$(echo "$V1" | tail -1)
[ "$HTTP_CODE" = "422" ] && check 0 "Empty message → 422" || check 1 "Empty message → 422 (got $HTTP_CODE)"

V2=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/chat" \
  -H "Content-Type: application/json" \
  -d "{\"session_id\":\"v2\",\"message\":\"   \"}")
HTTP_CODE=$(echo "$V2" | tail -1)
[ "$HTTP_CODE" = "422" ] && check 0 "Whitespace-only → 422" || check 1 "Whitespace-only → 422 (got $HTTP_CODE)"

V3=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/chat" \
  -H "Content-Type: application/json" \
  -d "not json")
HTTP_CODE=$(echo "$V3" | tail -1)
[ "$HTTP_CODE" = "422" ] && check 0 "Malformed JSON → 422" || check 1 "Malformed JSON → 422 (got $HTTP_CODE)"

# --- 7. History & 404 ---
echo ""
echo "--- History ---"
HIST=$(curl -s -w "\n%{http_code}" "$BASE_URL/sessions/$SESSION_ID/messages")
HTTP_CODE=$(echo "$HIST" | tail -1)
BODY=$(echo "$HIST" | sed '$d')
[ "$HTTP_CODE" = "200" ] && check 0 "GET /sessions/.../messages → 200" || check 1 "GET /sessions/.../messages → 200 (got $HTTP_CODE)"
echo "$BODY" | "$PYTHON_BIN" -c "
import sys,json; d=json.load(sys.stdin)
assert d['session_id']=='$SESSION_ID'
assert len(d['messages'])>=2
assert d['messages'][0]['role']=='user'
assert d['messages'][1]['role']=='assistant'
assert 'metadata' in d['messages'][1]
" 2>/dev/null && check 0 "History shape" || check 1 "History shape"

H404=$(curl -s -w "\n%{http_code}" "$BASE_URL/sessions/nonexistent-xyz/messages")
HTTP_CODE=$(echo "$H404" | tail -1)
BODY=$(echo "$H404" | sed '$d')
[ "$HTTP_CODE" = "404" ] && check 0 "Unknown session → 404" || check 1 "Unknown session → 404 (got $HTTP_CODE)"
echo "$BODY" | "$PYTHON_BIN" -c "import sys,json; d=json.load(sys.stdin); assert d['detail']=='session not found'" 2>/dev/null \
  && check 0 "404 detail message" || check 1 "404 detail message"

# --- Summary ---
echo ""
echo "====================================="
echo "  PASS: $PASS   FAIL: $FAIL"
echo "====================================="
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
