# Submission Checklist & Form Preparation

Use this guide to complete the **Lyftr AI Assignment Submission Form**.

---

## 1. Deliverables Required

| Deliverable | Status / Where to find | Notes |
|---|---|---|
| **Public GitHub Repository URL** | `https://github.com/<your-username>/<your-repo-name>` | See section 2 below to push |
| **Frontend Live URL** | `https://<your-app>.vercel.app` (or Netlify/Render) | Deployed via Vercel/Netlify |
| **Backend Live URL** | `https://<your-backend>.onrender.com` (or Fly.io) | Deployed via Render with persistent disk |
| **2–3 Minute Demo Video URL** | Loom / YouTube / Google Drive link | Follow `DEMO_SCRIPT.md` |

---

## 2. Pushing to GitHub

All files are committed locally on branch `main`. Run:

```bash
# 1. Create a new public repository on GitHub (e.g. named lyftr-llm-chatbot)
# 2. In this project folder, connect the remote and push:
git remote add origin https://github.com/<YOUR_GITHUB_USERNAME>/<YOUR_REPO_NAME>.git
git branch -M main
git push -u origin main
```

---

## 3. Fast Deployment Steps

### Backend (Render - Free / Starter)
1. Go to https://dashboard.render.com → **New** → **Web Service**
2. Connect your GitHub repository.
3. Select **Docker** environment.
   - **Dockerfile Path:** `./backend/Dockerfile`
   - **Docker Context:** `./backend`
4. Add **Persistent Disk**:
   - **Name:** `chatbot-data`
   - **Mount Path:** `/data`
   - **Size:** 1 GB
5. Add Environment Variables:
   - `LLM_API_KEYS`: `your-key-1,your-key-2` (at least 2 valid keys from Google AI Studio / Gemini)
   - `ALLOWED_ORIGINS`: `https://<your-frontend>.vercel.app` (or `*` temporarily)
   - `ENABLE_FAILURE_SIMULATION`: `true`
   - `DATABASE_URL`: `sqlite:////data/app.db`
   - `CACHE_DIR`: `/data/cache`
   - `LLM_MODEL`: `gemini/gemini-2.0-flash`
6. Click **Create Web Service**. Verify with: `https://<your-backend>.onrender.com/health`

### Frontend (Vercel - Free)
1. Go to https://vercel.com → **Add New Project**
2. Import your GitHub repository.
3. Configuration:
   - **Framework Preset:** Vite
   - **Root Directory:** `frontend`
4. Environment Variables:
   - `VITE_API_URL`: `https://<your-backend>.onrender.com`
5. Click **Deploy**.

---

## 4. Verification Check Before Submitting

Run the smoke test script against your live backend:

```bash
python scripts/smoke_test.py https://<your-backend>.onrender.com
```

Confirm that:
- [x] All 21 tests pass in `backend/tests/test_api.py`
- [x] `GET /health` returns `200` with `status: ok`, `keys_configured >= 2`, `cache_enabled: true`
- [x] Live UI shows metadata badges next to each assistant reply
- [x] Repeated first message in a new session returns green `LLM_CACHE`
- [x] `X-Simulate-Failure: key_1=429` shows `key_2` with 1 fallback attempt
- [x] `X-Simulate-Failure: *=429` shows clean inline error `all providers unavailable` (503)
- [x] Data persists after restarting the container/server
