import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import scheduler, streaming
from .config import settings
from .routers import alerts, auth, chat, markets, watchlist

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.start()
    yield
    scheduler.stop()


app = FastAPI(title="Stock Scraper API", version="0.1.0", lifespan=lifespan)

# Paths that must stay reachable before signing in.
AUTH_EXEMPT = {
    "/api/auth/login",
    "/api/auth/signup",
    "/api/auth/forgot",
    "/api/auth/reset",
    "/api/auth/status",
    "/api/health",
}


# Registered BEFORE CORSMiddleware below, so CORS wraps auth and 401 responses
# still carry CORS headers (the browser can read them and show the login).
@app.middleware("http")
async def require_dashboard_auth(request, call_next):
    path = request.url.path
    if (
        settings.dashboard_password
        and path.startswith("/api")
        and path not in AUTH_EXEMPT
        and request.method != "OPTIONS"
        and not auth.token_ok(request)
    ):
        return JSONResponse({"detail": "Password required"}, status_code=401)
    return await call_next(request)


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

app.include_router(auth.router, prefix="/api")
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
