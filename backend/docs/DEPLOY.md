# Deployment Guide

## Backend: Render (Docker with Persistent Disk)

### Step-by-step

1. **Create a Render account** at https://render.com if you don't have one.

2. **Create a new Web Service:**
   - Go to Dashboard → New → Web Service
   - Connect your GitHub/GitLab repository
   - Select the repository containing this project

3. **Configure the service:**
   - **Name:** `llm-chatbot-backend`
   - **Region:** Oregon (US West) or closest
   - **Runtime:** Docker
   - **Dockerfile Path:** `./backend/Dockerfile`
   - **Docker Context:** `./backend`
   - **Plan:** Starter or higher

4. **Add a Persistent Disk:**
   - Name: `chatbot-data`
   - Mount Path: `/data`
   - Size: 1 GB

5. **Set Environment Variables** (in Render dashboard → Environment):

   | Variable | Value |
   |----------|-------|
   | `LLM_API_KEYS` | `your-key-1,your-key-2` (at least 2 real API keys) |
   | `ALLOWED_ORIGINS` | `https://your-frontend.vercel.app` |
   | `ENABLE_FAILURE_SIMULATION` | `true` |
   | `DATABASE_URL` | `sqlite:////data/app.db` |
   | `CACHE_DIR` | `/data/cache` |
   | `LLM_MODEL` | `gemini/gemini-2.0-flash` |

6. **Deploy** — click "Create Web Service". Render will build and deploy automatically.

7. **Verify** the health endpoint: `curl https://your-backend.onrender.com/health`

### Alternative: Fly.io

1. Install `flyctl`: https://fly.io/docs/hands-on/install-flyctl/
2. Create `fly.toml` in the `backend/` directory:

```toml
app = "llm-chatbot-backend"
primary_region = "sjc"

[build]
  dockerfile = "Dockerfile"

[http_service]
  internal_port = 8000
  force_https = true
  auto_stop_machines = true
  auto_start_machines = true

[mounts]
  source = "chatbot_data"
  destination = "/data"
```

3. Launch:
```bash
cd backend
fly launch --no-deploy
fly volumes create chatbot_data --size 1 --region sjc
fly secrets set LLM_API_KEYS="key1,key2" ALLOWED_ORIGINS="https://your-frontend.vercel.app" ENABLE_FAILURE_SIMULATION="true"
fly deploy
```

---

## Frontend: Vercel

### Step-by-step

1. **Create a Vercel account** at https://vercel.com if you don't have one.

2. **Import the project:**
   - Go to Dashboard → Add New → Project
   - Import your Git repository

3. **Configure the project:**
   - **Framework Preset:** Vite
   - **Root Directory:** `frontend`
   - **Build Command:** `npm run build`
   - **Output Directory:** `dist`

4. **Set Environment Variables:**

   | Variable | Value |
   |----------|-------|
   | `VITE_API_URL` | `https://your-backend.onrender.com` |

5. **Deploy** — click Deploy. Vercel builds and deploys automatically.

6. **Update ALLOWED_ORIGINS** on the backend to include your Vercel URL.

### Alternative: Netlify

1. Create a Netlify account at https://www.netlify.com
2. New site → Import from Git → Select your repo
3. Build settings:
   - Base directory: `frontend`
   - Build command: `npm run build`
   - Publish directory: `frontend/dist`
4. Environment: `VITE_API_URL=https://your-backend.onrender.com`
5. Add a `_redirects` file in `frontend/public/`:
   ```
   /* /index.html 200
   ```

---

## Post-Deploy Checklist

- [ ] Backend health check returns 200 with `keys_configured >= 2`
- [ ] Frontend loads and shows the chat UI (not "waking up server...")
- [ ] Send a message → get a response with metadata
- [ ] Send the same message in a new chat → see LLM_CACHE (green badge)
- [ ] Use Test Tools → key_1=429 → see key_2 answering with 1 fallback
- [ ] Use Test Tools → *=429 → see error message in chat
- [ ] Check history endpoint: `curl <backend>/sessions/<id>/messages`
- [ ] Run the smoke test: `bash scripts/smoke_test.sh <BACKEND_URL>`
- [ ] CORS is properly configured (no errors in browser console)
- [ ] Data persists after a backend restart (send message, restart, check history)
