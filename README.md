# Market Dashboard

A personal web app for understanding the stock market and macro events. It
scrapes live market data (stocks, indices, commodities, bonds), shows graphs and
stats, summarizes how each asset class moved over the day/week/month, and uses AI
to explain *why* — tying real-world macro events to the price moves you see.

Runs locally first; built so it can be deployed to the web later to share.

## Architecture

```
Stock Scraper Project/
├── backend/          FastAPI service (Python) — data + AI narratives
│   └── app/
│       ├── main.py            FastAPI app, CORS, lifespan
│       ├── config.py          settings / .env loading
│       ├── universe.py        the tracked instruments + display names
│       ├── scheduler.py       background refresh loop (keeps data current)
│       ├── providers/
│       │   ├── market.py      yfinance: quotes, history, overview, summaries
│       │   └── narrative.py   macro "why did it move" (Claude when configured)
│       └── routers/markets.py HTTP API
└── frontend/         Next.js app (React/TypeScript) — the UI  [coming next]
```

**Data sources:**
- Prices/charts: [Twelve Data](https://twelvedata.com/) (real-time) when
  `TWELVE_DATA_API_KEY` is set — used for stocks, ETFs, FX, and spot
  gold/silver/oil — with [yfinance](https://github.com/ranaroussi/yfinance)
  (Yahoo) as the automatic fallback for everything else (indices, the dollar
  index, Treasury yields, other commodities) and when no key is present.
- News & analyst consensus: yfinance (Yahoo). Economic data: FRED (no key).
- AI summaries/narratives: Anthropic API (optional).

The app runs fully on yfinance with **no keys at all**; the keys only add
real-time data (Twelve Data) and AI writeups (Anthropic).

## Running the backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Then open <http://localhost:8000/docs> for the interactive API explorer.

### Optional configuration

Copy `backend/.env.example` to `backend/.env` and fill in keys to unlock extra
features. **Everything works without any keys** — they only add the AI macro
narratives (`ANTHROPIC_API_KEY`) and, later, richer economic data (`FRED_API_KEY`).

## API endpoints (v0.1)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Liveness + whether AI is enabled |
| GET | `/api/universe` | Tracked instruments by asset class |
| GET | `/api/overview` | Snapshot quote for every instrument |
| GET | `/api/summary?scope=day\|week\|month` | Gainers/losers + average move per class |
| GET | `/api/macro?scope=day\|week\|month` | Plain-English "why it moved" narrative |
| GET | `/api/quote/{symbol}` | Rich snapshot for one instrument |
| GET | `/api/history/{symbol}?range=1d…max` | OHLCV candles for charts |
| GET | `/api/search?q=` | Ticker/company autocomplete (any symbol) |
| GET | `/api/news` · `/api/news/{symbol}` | Market-wide and per-asset headlines |
| GET | `/api/economy` | FRED macro indicators + implications |
| GET | `/api/calendar` | Upcoming economic events + implications |
| GET | `/api/currencies` · `/api/convert?base=&quote=&amount=` | FX list + converter |
| GET | `/api/movers?scope=` | Top movers each paired with a headline |
| GET | `/api/article/{id}` | In-app article view: AI summary + linked assets |
| GET | `/api/analysis/{symbol}` | Analyst buy/hold/sell consensus + AI rationale |
| GET/POST/DELETE/PUT | `/api/watchlists[...]` | Named watchlists: CRUD + add/remove items |

Symbols are Yahoo tickers — URL-encode special characters (e.g. the S&P 500
`^GSPC` becomes `%5EGSPC`, gold `GC=F` becomes `GC%3DF`).

## Frontend pages

`/` dashboard (incl. "What moved & why") · `/economy` (indicators + calendar +
news) · `/currency` (rates + converter) · `/watchlist` (named lists) ·
`/asset/[symbol]` detail (chart, analyst consensus, news) · `/article/[id]`
(AI summary + linked assets). A nav search box autocompletes any ticker.

## Roadmap

- [x] Backend foundation: multi-asset data, summaries, AI narratives
- [x] Frontend: dashboard + per-asset detail pages with charts
- [x] Live auto-refresh in the UI (polling)
- [x] Macro/economic data layer (FRED) feeding the narratives
- [x] News headlines + in-app article pages with linked assets
- [x] Economic calendar with market implications
- [x] Currencies asset class + currency converter
- [x] Search with autocomplete
- [x] Multiple named watchlists
- [x] News tied to specific movers ("What moved & why")
- [x] Analyst buy/hold/sell consensus with AI bull/hold/bear rationale
- [x] Real-time prices via Twelve Data (stocks/ETFs/FX/metals) + yfinance fallback
- [x] Live WebSocket price streaming (prices tick & flash)
- [ ] Indices/commodities real-time (needs the Twelve Data index/commodity feed)
- [ ] Fetch full article text for richer summaries (currently headline-based)
- [ ] Per-user accounts (multi-device)
- [ ] Deploy to the web

More features to come.
