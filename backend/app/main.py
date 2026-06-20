import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from . import scheduler, streaming
from .config import settings
from .routers import markets, watchlist

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.start()
    yield
    scheduler.stop()


app = FastAPI(title="Stock Scraper API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(markets.router, prefix="/api")
app.include_router(watchlist.router, prefix="/api")


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
