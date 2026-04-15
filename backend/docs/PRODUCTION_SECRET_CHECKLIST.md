# Production Secret Checklist

Last Updated: 2026-04-03

Use this before enabling production traffic.

## Required Secrets

1. `DATABASE_URL` (Neon production branch)
2. `AUTH_SECRET_KEY` (32+ chars, random)
3. `REDIS_URL` (Render Redis internal URL with auth)
4. `FIRECRAWL_API_KEY`

## Required Non-Secret Production Config

1. `ENVIRONMENT=production`
2. `DEBUG=false`
3. `AUTH_COOKIE_SECURE=true`
4. `QUEUE_DRIVER=dramatiq`
5. `LOG_LEVEL=INFO`

## Secret Hygiene Rules

1. Never commit real values to Git.
2. Rotate `AUTH_SECRET_KEY` and API keys on incident or exposure.
3. Keep separate credentials for staging and production.
4. Restrict secret access to deployment owners only.
5. Verify all secrets are set for both API and worker services.

## Pre-Traffic Verification

1. API boot success with production env.
2. Worker boot success with production env.
3. `GET /health` and `GET /api/v1/health` healthy.
4. Small canary flow successful before full traffic.
