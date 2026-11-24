# 2–3 Minute Demo Video Script (Lyftr AI Full-Stack Assignment)

This script is structured and timed to hit **10/10 points** on the evaluation rubric within **2 to 3 minutes**.

---

### Timing & Scene Breakdown

```
 0:00 - 0:25  | Scene 1: Introduction & Architecture Overview
 0:25 - 0:55  | Scene 2: Live Chat & Multi-Turn Conversation
 0:55 - 1:30  | Scene 3: Response Caching (Live vs LLM_CACHE)
 1:30 - 2:10  | Scene 4: Key Failover & Simulation Hook (key_1=429 & *=429)
 2:10 - 2:35  | Scene 5: Persistence & API Contract
 2:35 - 2:50  | Scene 6: Conclusion
```

---

### Scene 1: Introduction (0:00 – 0:25)
**Screen:** Show the deployed frontend application in your browser.
**Action:** Point to the UI header, test tools toggle, and clean chat layout.
**Spoken Voiceover:**
> *"Hi everyone, welcome to my demo of the Lyftr AI Full-Stack Assignment. Today I'm demonstrating an end-to-end LLM chatbot featuring multi-turn conversation memory, an API-key pool with automatic failover, and LiteLLM response caching. The stack uses React, TypeScript, and Tailwind on the frontend, FastAPI and LiteLLM on the backend, and SQLite in WAL mode with a persistent disk volume for session storage."*

---

### Scene 2: Live Chat & Multi-Turn Memory (0:25 – 0:55)
**Screen:** Live chat window.
**Action:**
1. Type: `"My favorite programming language is Python. Remember this."` and press Enter.
2. Wait for reply. Point out the metadata badge:
   - Badge: `LIVE_INFERENCE` (blue)
   - Model name, e.g., `gemini/gemini-2.0-flash`
   - Latency (e.g., ~750 ms)
   - Input and output tokens (per-request only)
   - Answering key ID: `key_1 · 0 fallback`
3. Type: `"What is my favorite language?"` and press Enter.
4. Show the bot answering `"Python"` correctly.
**Spoken Voiceover:**
> *"Let's test multi-turn state. First, I tell the bot my favorite language is Python. Notice the metadata right next to the reply: it shows `LIVE_INFERENCE`, the exact model, the server-measured latency, input and output tokens for this request, and key_1 as the answering provider. Now I ask what my favorite language was, and it answers accurately from SQLite session history—confirming multi-turn context retention."*

---

### Scene 3: Response Caching (0:55 – 1:30)
**Screen:** Live chat window.
**Action:**
1. Click **"New chat"** button in the header. (Notice a new session ID is generated).
2. Type: `"What is the capital of France?"` and press Enter.
   - Point out: Source is `LIVE_INFERENCE` (blue), answering key `key_1`, latency around 800 ms.
3. Click **"New chat"** again to start a fresh session.
4. Type the exact same message: `"What is the capital of France?"` and press Enter.
   - Point out: Badge turns **green** `LLM_CACHE`.
   - Latency drops significantly (e.g. 5–20 ms).
   - Answering key is `null` (since it came from disk cache).
   - Reply text and token usage are preserved.
**Spoken Voiceover:**
> *"Now let's verify response caching. I start a new session and ask 'What is the capital of France?'. The first call is a `LIVE_INFERENCE` taking around 800 ms. Now I open a completely new chat session and ask the exact same first question. Notice the badge turns green: `LLM_CACHE`. The latency dropped to just a few milliseconds, key ID is null, and the reply is identical. The cache key is a deterministic SHA-256 of the model and message sequence, excluding API keys."*

---

### Scene 4: Key Failover with X-Simulate-Failure (1:30 – 2:10)
**Screen:** Live chat window with **"Test tools"** opened.
**Action:**
1. Click **"Test tools"** toggle.
2. In the dropdown, select `key_1=429`.
3. Type `"Tell me a short joke"` and click Send.
   - Point out: The request succeeds with 200 OK!
   - Metadata shows: `key_2 · 1 fallback`.
4. Now select `*=429 (all fail)` from the dropdown.
5. Type `"Hello again"` and click Send.
   - Point out: A readable error appears in the UI: `⚠️ all providers unavailable`.
   - No broken screen, no stack trace, no unhandled exception.
**Spoken Voiceover:**
> *"Next, let's verify system resilience using the failure simulation hook. In Test Tools, I select `key_1=429`, sending the `X-Simulate-Failure` header. When I send a message, key_1 is intercepted, and the gateway seamlessly fails over to `key_2`. The user receives a real answer with 200 OK, and metadata displays `key_2` with 1 fallback attempt. Next, I simulate `*=429` where all keys are rate-limited. The app cleanly surfaces an inline error message: 'all providers unavailable' with HTTP 503—never a blank screen or unhandled exception."*

---

### Scene 5: SQLite Persistence & Contract Verification (2:10 – 2:35)
**Screen:** Show terminal / browser tab with `GET /health` and `GET /sessions/<id>/messages`.
**Action:**
1. Refresh or show the `/health` endpoint returning:
   `{"status": "ok", "keys_configured": 2, "cache_enabled": true}`.
2. Highlight that all messages and metadata are persisted in SQLite WAL mode.
**Spoken Voiceover:**
> *"Behind the scenes, the `/health` endpoint confirms that database reachability and the key pool are healthy. The test suite includes 21 comprehensive pytest cases verifying error handling, session isolation, token tracking, and contract compliance."*

---

### Scene 6: Wrap-Up (2:35 – 2:50)
**Screen:** Back to the clean UI.
**Spoken Voiceover:**
> *"The repository includes multi-stage Dockerfiles, a Docker Compose setup with persistent volume mounting, a Makefile for one-command local execution with `make up`, and full deployment configurations. Thank you for watching!"*
