# Upwork Automation — Free Deployment Guide (Inline Mode)

**Last updated:** April 15, 2026
**Total cost:** $0/month forever
**Stack:** FastAPI · React/Vite · Neon Postgres (no Redis, no worker)
**Code status:** ✅ CORS middleware applied — ready to deploy

---

## 1. Architecture (2 deployments, $0/month)

Only **2 things** to deploy. Jobs run synchronously inside HTTP requests — no queue, no worker, no Redis.

| # | Component | Host | Plan | Cost |
|---|---|---|---|---|
| 1 | Backend | Render Web Service | Free | $0 |
| 2 | Frontend (React SPA) | Render Static Site | Free | $0 |
| — | Postgres | Neon (existing) | Free | $0 |

### How it works

```
┌────────────────────────────┐
│  Render Free Web Service   │
│  FastAPI (inline mode)     │
└──────────────┬─────────────┘
               │
               ▼
         Neon Postgres
               ▲
               │
       Render Static (Frontend)
```

- User clicks "Generate proposal" → FastAPI runs the AI call directly in the HTTP request
- Response returns after 60–120 seconds with the result
- No queue, no worker threads, no Redis polling

### Tradeoff — be aware

Render's free tier kills any HTTP request that runs **longer than 100 seconds**. This means:
- Short AI calls (<100s): work fine
- Long 4-artifact generations (>100s): occasionally time out with 502 → user retries
- Multiple concurrent users: each request blocks others on the single free instance

**No code errors.** Just occasional 502s from Render's proxy. Fine for demo / MVP / light usage. If you need bulletproof async generation, upgrade to a paid worker service later.

### Why not Dramatiq + Upstash

Dramatiq's worker polls Redis constantly even when idle (~14,000 commands/hour per idle worker). Upstash's 10k/day free limit gets exhausted in under an hour. The combination is not viable on free tiers.

---

## 2. Code changes (already applied ✅)

Two files were edited. You don't need to do anything — just confirm these exist in your repo before pushing.

### 2.1 [backend/app/infrastructure/config/settings.py](../backend/app/infrastructure/config/settings.py)

Added `cors_allowed_origins` field + `cors_origins_list` property.

```python
cors_allowed_origins: str = ""

@property
def cors_origins_list(self) -> list[str]:
    if not self.cors_allowed_origins.strip():
        return []
    return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]
```

### 2.2 [backend/app/main.py](../backend/app/main.py)

**CORS middleware** registered first so preflight OPTIONS requests never get blocked by rate limiting.

```python
if settings.cors_origins_list:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
        max_age=600,
    )
```

**Note on in-process worker:** The lifespan hook also contains logic to start Dramatiq workers if `QUEUE_DRIVER=dramatiq`. In inline mode (our choice), `is_dramatiq_enabled()` returns `False` and the worker block is skipped entirely. No Redis connection, no polling, no idle cost. Keep the code — it's dormant until you choose to re-enable async mode later.

---

## 3. Prerequisites

### 3.1 Accounts

Render · Upstash · Neon (existing) · Google Cloud · OpenAI · Anthropic · Firecrawl · GitHub

### 3.2 Push code to GitHub

```bash
cd c:/Users/priya/Desktop/Ladder/Upwork_automation

# Confirm no real .env is staged:
git ls-files | grep -i "\.env$"     # must return nothing

git init                              # if not already a repo
git add .
git commit -m "Prepare for deployment"
git remote add origin https://github.com/<you>/upwork-automation.git
git branch -M main
git push -u origin main
```

### 3.3 Database URL — no manual conversion needed

Good news: [settings.py](../backend/app/infrastructure/config/settings.py) has a validator that **automatically converts** any Neon URL format. You can paste your existing URL as-is:

```
postgresql://neondb_owner:npg_al8HiOcnVvk0@ep-orange-leaf-am931yx8-pooler.c-5.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require
```

The validator converts to `postgresql+asyncpg://...?ssl=require` and strips `channel_binding` automatically.

### 3.4 Google Cloud OAuth

Lock in Render service names (they become permanent URLs):
- Backend: `upwork-backend` → `https://upwork-backend.onrender.com`
- Frontend: `upwork-frontend` → `https://upwork-frontend.onrender.com`

In Google Cloud Console:
1. Enable **Google Docs API** + **Google Drive API**
2. OAuth consent screen → External → add yourself as test user
3. Credentials → Create OAuth client ID → Web application
   - **Authorized JavaScript origins:** `https://upwork-frontend.onrender.com`
   - **Authorized redirect URIs:** `https://upwork-backend.onrender.com/api/v1/connectors/google/callback`
4. Copy Client ID and Secret

Match byte-for-byte — a trailing-slash mismatch breaks OAuth with `redirect_uri_mismatch`.

### 3.5 Rotate exposed secrets before deploy

Your current `.env` was shared in our conversation — regenerate these:

- `OPENAI_API_KEY` — platform.openai.com/api-keys
- `ANTHROPIC_API_KEY` — console.anthropic.com/settings/keys
- `FIRECRAWL_API_KEY` — firecrawl.dev dashboard
- `GOOGLE_OAUTH_CLIENT_SECRET` — Google Cloud → rotate
- `NAPKIN_AI` — Napkin AI dashboard
- `AUTH_SECRET_KEY` — generate: `python -c "import secrets; print(secrets.token_urlsafe(48))"`

---

## 4. ~~Redis~~ — skipped in inline mode

No Redis needed. You can delete any Upstash database you already created — it won't be used. Skip straight to §5.

---

## 5. Deploy Backend (Render Web Service — runs both HTTP + worker)

1. Render dashboard → **New +** → **Web Service** → connect GitHub repo
2. Configure:
   - **Name:** `upwork-backend`
   - **Region:** closest to Neon
   - **Branch:** `main`
   - **Root Directory:** `backend`
   - **Runtime:** Python 3
   - **Build Command:**
     ```
     pip install -e . && alembic upgrade head
     ```
   - **Start Command:**
     ```
     uvicorn app.main:app --host 0.0.0.0 --port $PORT
     ```
   - **Instance Type:** **Free**
   - **Health Check Path:** `/health`
3. **Environment** tab → paste ALL vars from §7.1
4. Click **Create Web Service**

Logs should show:
- `alembic upgrade head` success
- `Uvicorn running on http://0.0.0.0:XXXX`
- **No** "Dramatiq worker started" message (correct — inline mode skips it)

### Keep backend awake (optional but recommended)

Render free sleeps after 15 min idle. Set up https://uptimerobot.com (free) to ping `https://upwork-backend.onrender.com/health` every 5 min.

---

## 6. Deploy Frontend (Render Static Site)

1. **New +** → **Static Site** → same GitHub repo
2. Configure:
   - **Name:** `upwork-frontend`
   - **Branch:** `main`
   - **Root Directory:** `frontend`
   - **Build Command:** `npm install && npm run build`
   - **Publish Directory:** `dist`
3. **Environment** tab → add §7.2 vars
4. Click **Create Static Site**

### 6.1 Add SPA rewrite rule (critical)

After first deploy:
1. Open static site → **Redirects/Rewrites** → **Add Rule**
2. Set:
   - **Source:** `/*`
   - **Destination:** `/index.html`
   - **Action:** **Rewrite** (not Redirect — status 200, transparent)
3. Save → trigger a redeploy

Without this, refreshing on `/workspace` returns 404.

---

## 7. Environment variables

### 7.1 Render Backend — exact env vars to paste

Copy-paste ready. These are your actual keys from `backend/.env` with the production changes applied. In Render dashboard → `upwork-backend` → **Environment** → click **Add Environment Variable** for each row, or use the **Secret Files** / bulk-add feature to paste all at once.

> ⚠️ **Security:** Real values live in `backend/.env` (gitignored — never committed). Placeholders below tell you which key to paste where. Render's "Add from .env" feature lets you paste the whole file at once.

```
APP_NAME=AgentLoopr Backend
ENVIRONMENT=production
DEBUG=false
HOST=0.0.0.0
LOG_LEVEL=INFO
API_PREFIX=/api/v1

DATABASE_URL=<paste Neon connection string — see backend/.env>

AUTH_SECRET_KEY=<paste from backend/.env OR regenerate fresh>
AUTH_ALGORITHM=HS256
AUTH_COOKIE_NAME=agentloopr_session
AUTH_SESSION_DAYS=35
AUTH_COOKIE_SECURE=true

CORS_ALLOWED_ORIGINS=https://upwork-frontend.onrender.com

LOGIN_RATE_LIMIT_ATTEMPTS=8
LOGIN_RATE_LIMIT_WINDOW_SECONDS=900
GLOBAL_RATE_LIMIT_REQUESTS=3000
GLOBAL_RATE_LIMIT_WINDOW_SECONDS=60
REQUEST_TIMEOUT_SECONDS=180
IDEMPOTENCY_TTL_SECONDS=3600
IDEMPOTENCY_MAX_ENTRIES=10000

QUEUE_DRIVER=inline
QUEUE_MAX_RETRIES=3

FIRECRAWL_BASE_URL=https://api.firecrawl.dev
FIRECRAWL_API_KEY=<paste from backend/.env>
FIRECRAWL_TIMEOUT_SECONDS=40
FIRECRAWL_MAX_RETRIES=2
FIRECRAWL_RETRY_BACKOFF_SECONDS=1.5

OPENAI_API_KEY=<paste from backend/.env>
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_TIMEOUT_SECONDS=30
OPENAI_MAX_RETRIES=2
OPENAI_RETRY_BACKOFF_SECONDS=1.0

ANTHROPIC_API_KEY=<paste from backend/.env>
ANTHROPIC_BASE_URL=https://api.anthropic.com
ANTHROPIC_API_VERSION=2023-06-01
ANTHROPIC_TIMEOUT_SECONDS=180
ANTHROPIC_MAX_RETRIES=1
ANTHROPIC_RETRY_BACKOFF_SECONDS=1.0

CONNECTOR_LIVE_HEALTH_TIMEOUT_SECONDS=8

GOOGLE_OAUTH_CLIENT_ID=<paste from backend/.env>
GOOGLE_OAUTH_CLIENT_SECRET=<paste from backend/.env>
GOOGLE_OAUTH_AUTHORIZE_URL=https://accounts.google.com/o/oauth2/v2/auth
GOOGLE_OAUTH_TOKEN_URL=https://oauth2.googleapis.com/token
GOOGLE_OAUTH_REDIRECT_URI=https://upwork-backend.onrender.com/api/v1/connectors/google/callback
GOOGLE_OAUTH_SCOPES=https://www.googleapis.com/auth/documents https://www.googleapis.com/auth/drive.file openid email profile
GOOGLE_OAUTH_STATE_TTL_SECONDS=600
GOOGLE_DOCS_API_BASE_URL=https://docs.googleapis.com/v1

AIRTABLE_PUBLISH_ENABLED=false
AIRTABLE_API_BASE_URL=https://api.airtable.com/v0
AIRTABLE_PERSONAL_ACCESS_TOKEN=<airtable_pat>

AI_MAX_INPUT_TOKENS_PER_RUN=12000
AI_MAX_OUTPUT_TOKENS_PER_RUN=6000
AI_DAILY_COST_LIMIT_USD=10.0
AI_ENABLE_SAFETY_GUARDRAILS=true
AI_PROVIDER_FAILURE_THRESHOLD=5
AI_PROVIDER_CIRCUIT_OPEN_SECONDS=60
AI_ENABLE_JOB_URL_LLM_FALLBACK=true
AI_JOB_URL_PARSER_MODEL=gpt-4o-mini
AI_JOB_URL_PARSER_MAX_OUTPUT_TOKENS=200

NAPKIN_AI=<paste from backend/.env>
```

### 7.1.1 Differences from your local `.env`

What changed vs your current `backend/.env`:

| Variable | Local (dev) | Render (production) |
|---|---|---|
| `ENVIRONMENT` | `development` | `production` |
| `DEBUG` | `true` | `false` |
| `PORT` | `8000` | **removed** (Render injects `$PORT` automatically) |
| `AUTH_COOKIE_SECURE` | `false` | `true` (HTTPS required) |
| `CORS_ALLOWED_ORIGINS` | (not present) | `https://upwork-frontend.onrender.com` (NEW — required for CORS) |
| `GOOGLE_OAUTH_REDIRECT_URI` | `http://localhost:8000/...` | `https://upwork-backend.onrender.com/...` |
| `QUEUE_DRIVER` | `dramatiq` (or `inline`) | `inline` (no Redis, no worker) |
| `REDIS_URL` | (Upstash URL) | **remove** — not needed in inline mode |

All other variables stay identical.

### 7.1.2 Don't forget to register the Google redirect in Google Cloud

The new production redirect URI (`https://upwork-backend.onrender.com/api/v1/connectors/google/callback`) must also be added to **Google Cloud Console → Credentials → your OAuth client → Authorized redirect URIs** (see §3.4). Keep the localhost one too so local dev still works.

### 7.2 Render Frontend Static Site — only 2 vars

```
VITE_API_BASE_URL=https://upwork-backend.onrender.com/api/v1
NODE_VERSION=20
```

Vite embeds `VITE_*` at **build time**. Changing later requires a redeploy.

### 7.3 Upstash / Neon

No env vars to set — they **give you** the URLs you paste into backend.

---

## 8. Verification (run in order)

| # | Test | Expected |
|---|---|---|
| 1 | `curl https://upwork-backend.onrender.com/health` | `{"status":"ok",...}` |
| 2 | Visit `https://upwork-frontend.onrender.com` | Login page loads |
| 3 | Register a user | 200 OK, session cookie set |
| 4 | Hard-refresh on `/workspace` | Loads (SPA rewrite works) |
| 5 | DevTools Network on any API call | OPTIONS preflight → 200 with `Access-Control-Allow-Origin` header |
| 6 | Connect Google → complete OAuth | Returns, connector shows connected |
| 7 | Submit Upwork job URL | Extraction completes in ~30s |
| 8 | Generate single-artifact output (e.g. proposal text) | Completes in 30–60s |
| 9 | Generate full 4-artifact output | Usually completes, **some will 502 after 100s** (accept it — click retry) |

If tests 1–8 pass, your deployment is healthy. Test 9 occasional failures are expected in inline mode on Render free tier.

---

## 9. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Build fails on `alembic upgrade head` | Wrong DB URL or Neon unreachable | Check `DATABASE_URL` — validator auto-converts so any Neon format works |
| `No 'Access-Control-Allow-Origin' header` | `CORS_ALLOWED_ORIGINS` missing/typo | Must match frontend URL exactly — no trailing slash |
| Refresh `/workspace` → 404 | SPA rewrite not configured | Add `/*` → `/index.html` **Rewrite** (not Redirect) |
| `redirect_uri_mismatch` on Google OAuth | Google Cloud URL ≠ env var | Match byte-for-byte, case-sensitive |
| 502 Bad Gateway on proposal generation | Render's 100s HTTP timeout killed the request | Normal in inline mode — retry, or upgrade to async later |
| Request hangs forever on generation | AI provider (OpenAI/Anthropic) slow | Check `OPENAI_TIMEOUT_SECONDS` / `ANTHROPIC_TIMEOUT_SECONDS` env vars |
| Out-of-memory during generation | 512 MB too tight | Inline mode uses less memory than async; if still OOM, reduce `AI_MAX_INPUT_TOKENS_PER_RUN` |
| Cold start 30s | Render free sleeps after 15 min | Set up UptimeRobot ping to `/health` every 5 min |
| Upstash 429 errors | 10k commands/day hit | Reduce polling frequency or upgrade |
| Session cookie doesn't stick | Accessing via `http://` not `https://` | Always use `https://` — `AUTH_COOKIE_SECURE=true` requires TLS |

---

## 10. Final checklist

### Pre-deploy
- [x] CORS + worker code changes applied (already done)
- [ ] Code pushed to GitHub, `.env` files NOT committed
- [ ] Exposed API keys rotated (§3.5)
- [ ] Fresh `AUTH_SECRET_KEY` generated
- [ ] Google Cloud OAuth client created with production URLs

### Deploy
- [ ] Render Web Service created with all §7.1 env vars
- [ ] Render Static Site created with §7.2 env vars
- [ ] SPA rewrite rule added to static site (§6.1)

### Post-deploy
- [ ] All 9 verification tests pass
- [ ] UptimeRobot configured (optional)

Once every box ticks, you're live on $0/month. Long generations may 502 occasionally — that's the tradeoff for inline mode on Render free tier.
