import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from . import scheduler, streaming
from .config import settings
from .routers import alerts, chat, markets, watchlist

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.start()
    yield
    scheduler.stop()


app = FastAPI(title="Stock Scraper API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    # Explicit origins (localhost + any custom domain you add to CORS_ORIGINS)...
    allow_origins=settings.cors_origin_list,
    # ...plus every Vercel deployment (production + per-commit preview URLs).
    allow_origin_regex=r"https://[a-z0-9-]+\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(markets.router, prefix="/api")
app.include_router(watchlist.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(alerts.router, prefix="/api")


@app.websocket("/ws/prices")
async def ws_prices(client: WebSocket):
    await streaming.stream_prices(client)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "ai_enabled": bool(settings.anthropic_api_key),
        "realtime": bool(settings.twelve_data_api_key),
        "price_source": "twelvedata" if settings.twelve_data_api_key else "yfinance",
    }
