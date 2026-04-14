# Deploying SurakshaPay (Phase 2)

This file is **additive** — the main documentation stays in the project README.

## What evaluators expect (end-to-end)

1. **Deployed URL** — host the API and the static frontend so judges can open a link.
2. **Runnable locally** — `docker compose` or backend + frontend dev servers with `env` setup.
3. **Packaged solution** — Docker images in this repo build reproducibly.

## Architecture

- **Backend:** FastAPI on port `8000` (`backend/Dockerfile`).
- **Frontend:** Vite build served by nginx with `/api` proxied to the backend (`frontend/Dockerfile`, `frontend/nginx.docker.conf`).

## Option A — Docker Compose (single machine / VM)

From the repo root:

```bash
docker compose up --build
```

- API (from browser): `http://localhost:8000`
- UI (nginx → proxies `/api` to backend): `http://localhost:5173` (mapped in `docker-compose.yml`)

Set `CORS_ORIGINS` in `backend/.env` to your public UI origin when you expose the app.

## Option B — Split deploy (typical cloud)

1. **Backend** — Deploy `backend/` as a Docker web service (Render, Fly.io, Railway, Azure Container Apps, etc.).
   - Set `DATABASE_URL` (SQLite is fine for demos; use Postgres for production).
   - Set secrets: JWT, Razorpay test keys, `OPENWEATHER_API_KEY`, `WAQI_API_TOKEN`, `CORS_ORIGINS=https://your-frontend.example.com`.
2. **Frontend** — Build with `VITE_API_BASE=https://your-api.example.com` (full URL to the API, no `/api` suffix unless your API is mounted that way).
   - Deploy `frontend/dist` to Netlify, Vercel, S3+CloudFront, or nginx.

## Option C — Render (blueprint-style)

- Create two services: **Web Service** (Docker) using `backend/Dockerfile`, and **Static Site** or second web service for the frontend build.
- Point frontend `VITE_API_BASE` at the public API URL.
- Add health check path: `GET /health`

## GPS / mobile WebView

- Real **device GPS** is captured in the dashboard (browser `navigator.geolocation`). Users must **allow location** and use **HTTPS** (or `localhost`) so the browser permits the API.
- Native Capacitor builds already use cleartext/dev settings from `capacitor.config.ts`; set `VITE_API_BASE` to your deployed API for production shells.

## Fraud / MSTS

Server-side checks include **haversine zone validation**, **Isolation Forest**-style scoring on engineered features, **multi-signal trust** (movement, accuracy noise, teleport speed, swarm load), and **duplicate paid-event** guards. See `backend/app/services/fraud.py` (implementation) and the README sections on fraud and adversarial defense (conceptual).
