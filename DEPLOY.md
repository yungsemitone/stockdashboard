# Deploying

Two pieces, deployed separately:

- **Backend** (FastAPI) → **Render** — an always-on Docker web service.
- **Frontend** (Next.js) → **Vercel** — free, auto HTTPS.

Your API keys are set as secrets in each host's dashboard and **never live in the
repo** (`.env` files are gitignored).

> The repo is already `git init`-ed locally with an initial commit. The steps
> below are the parts only you can do (creating accounts, pushing, setting
> secrets). Ping me to verify once it's live.

---

## 0 · Push the code to GitHub

Create an empty repo on github.com (e.g. `markets-dashboard`), then:

```bash
git remote add origin https://github.com/<you>/markets-dashboard.git
git push -u origin main
```

## 1 · Backend on Render

1. Sign in at **render.com** (logging in with GitHub is easiest).
2. **New → Blueprint** → pick this repo. Render reads `render.yaml` and creates
   the `markets-backend` Docker service with a 1 GB persistent disk.
3. In the service's **Environment** tab, set the secret values:
   - `TWELVE_DATA_API_KEY` → your Twelve Data key
   - `ANTHROPIC_API_KEY` → your Anthropic key
   - `CORS_ORIGINS` → leave blank for now (set in step 3 once you have the Vercel URL)
4. Click **Deploy** and wait for **Live**. Copy the URL, e.g.
   `https://markets-backend.onrender.com`.
5. Sanity check: open `https://markets-backend.onrender.com/api/health` — it
   should show `"realtime": true` and `"ai_enabled": true`.

## 2 · Frontend on Vercel

1. Sign in at **vercel.com** (GitHub login).
2. **Add New → Project** → import the same repo.
3. Set **Root Directory = `frontend`**.
4. Add an environment variable:
   - `NEXT_PUBLIC_API_URL` → your backend URL from step 1
     (`https://markets-backend.onrender.com`)
5. **Deploy**. Copy the URL, e.g. `https://your-app.vercel.app`.

## 3 · Connect them (CORS)

1. Render → `markets-backend` → **Environment** → set
   `CORS_ORIGINS = https://your-app.vercel.app` → save (it redeploys).
2. Open your Vercel URL. The dashboard loads live data and prices tick in
   real time (WebSocket runs over `wss://` automatically).

## Updating later

`git push` → **both** Render and Vercel auto-redeploy. Nothing else to do.

---

## Notes & caveats

- **Always-on:** the Render **Starter** plan keeps the process running so the
  60-second refresh scheduler stays alive and data stays current. The *free*
  plan sleeps after ~15 min idle (stale data), so it's not suitable here.
- **yfinance from the cloud:** indices, news, the analyst consensus, and market
  cap come from Yahoo via yfinance, which can throttle cloud IPs. Twelve Data
  (stock/FX/metal prices + streaming) is unaffected. If the Yahoo-sourced parts
  get flaky in production, we can add caching/retries or a proxy — tell me and
  I'll harden it.
- **Watchlists** persist on the Render disk (`DATA_DIR=/var/data`) across
  redeploys.
- **Other hosts:** the backend is a standard Dockerfile, so Railway / Fly.io / a
  VPS work too — point them at `backend/Dockerfile` and set the same env vars
  (plus a mounted volume at whatever you set `DATA_DIR` to).
