# Deploying

Two pieces, deployed separately:

- **Backend** (FastAPI) → **Fly.io** — an always-on Docker machine.
- **Frontend** (Next.js) → **Vercel** — free, auto HTTPS.

Your API keys are set as secrets in each host (via CLI / dashboard) and **never
live in the repo** (`.env` files are gitignored).

> The repo is already `git init`-ed locally with an initial commit, and the
> backend Docker image is verified to build + boot. The steps below are the
> parts only you can do (accounts, pushing, secrets, deploy). Ping me to verify
> once it's live.

---

## 0 · Push the code to GitHub

Needed for Vercel (and version control). Fly deploys straight from your local
folder, so it doesn't strictly need GitHub.

Create an empty repo on github.com, then:

```bash
git remote add origin https://github.com/<you>/<repo>.git
git push -u origin main
```

## 1 · Backend on Fly.io

You already have `flyctl` installed. Run everything from the `backend/` folder
(that's where `fly.toml` + the `Dockerfile` live):

```bash
cd backend
fly auth login                         # opens browser; sign up / log in

# 1. Edit fly.toml: set  app = "your-unique-name"  (and primary_region if you like)
fly apps create your-unique-name

# 2. Persistent volume for watchlists (region MUST match primary_region in fly.toml)
fly volumes create data --size 1 --region iad

# 3. Secrets — encrypted, never in the repo
fly secrets set TWELVE_DATA_API_KEY=your_twelve_data_key ANTHROPIC_API_KEY=your_anthropic_key

# 4. Deploy
fly deploy
```

Your backend is now at `https://your-unique-name.fly.dev`. Check
`https://your-unique-name.fly.dev/api/health` — it should show
`"realtime": true` and `"ai_enabled": true`.

**Always-on:** `fly.toml` sets `auto_stop_machines = false` and
`min_machines_running = 1`, so the machine runs 24/7 and the 60-second data
scheduler never sleeps.

## 2 · Frontend on Vercel

1. Sign in at **vercel.com** (GitHub login).
2. **Add New → Project** → import the repo.
3. Set **Root Directory = `frontend`**.
4. Add an environment variable:
   - `NEXT_PUBLIC_API_URL` → `https://your-unique-name.fly.dev`
5. **Deploy**. Copy the URL, e.g. `https://your-app.vercel.app`.

## 3 · Connect them (CORS)

```bash
cd backend
fly secrets set CORS_ORIGINS=https://your-app.vercel.app   # your Vercel URL
```

Fly redeploys automatically when secrets change. Open your Vercel URL — the
dashboard loads live data and prices tick in real time (WebSocket runs over
`wss://` automatically).

## Updating later (auto-deploy on push)

Both halves redeploy on `git push` to `main`:

- **Frontend:** Vercel auto-redeploys (built in).
- **Backend:** a GitHub Action (`.github/workflows/fly-deploy.yml`) deploys to
  Fly. **One-time setup** — create a deploy token and add it as a repo secret:
  ```bash
  cd backend
  fly tokens create deploy -x 8760h    # prints a token (valid 1 year)
  ```
  On GitHub: repo → **Settings → Secrets and variables → Actions → New
  repository secret** → name `FLY_API_TOKEN`, value = that token.
  After that, any push touching `backend/` deploys automatically (or trigger it
  from the **Actions** tab). Until the token is set, deploy manually:
  `cd backend && fly deploy`.

## Custom domain (optional)

Needs a domain you own (any registrar).

1. **Vercel** → project → **Settings → Domains** → add your domain and follow
   the DNS records it shows you (set them at your registrar).
2. Let the backend accept it (every `*.vercel.app` URL is already allowed, but a
   custom domain must be added explicitly):
   ```bash
   cd backend
   fly secrets set CORS_ORIGINS="https://yourdomain.com,https://www.yourdomain.com"
   ```

---

## Notes & caveats

- **yfinance from the cloud:** indices, news, the analyst consensus, and market
  cap come from Yahoo via yfinance, which can throttle cloud IPs. Twelve Data
  (stock/FX/metal prices + streaming) is unaffected. If the Yahoo-sourced parts
  get flaky in production, we can add caching/retries or a proxy — tell me and
  I'll harden it.
- **Watchlists** persist on the Fly volume (`DATA_DIR=/var/data`) across deploys.
- **Verified locally:** `docker build` + run of `backend/Dockerfile` boots and
  serves `/api/health` — the same image Fly builds.
- **Prefer Render instead?** A `render.yaml` blueprint is also in the repo; the
  Dockerfile is identical, so Render / Railway / a VPS work too — just set the
  same env vars and a mounted volume at `DATA_DIR`.
```
