from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import auth, webhook, users, trades, bots, billing, admin, positions, ea_bridge
from app.config import FRONTEND_URL
import logging

# Configure logging for the application
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)
logger.info("DominanceBot API Starting up...")

app = FastAPI(
    title="DominanceBot API",
    description="Trading SaaS Platform API",
    version="1.0.0"
)

# Critical Fix #4 — CORS so the Next.js frontend can reach the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost",
        "http://localhost:3000",
        "http://127.0.0.1",
        "http://127.0.0.1:3000",
        FRONTEND_URL,
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(webhook.router, prefix="/api", tags=["Webhook"])
app.include_router(ea_bridge.router, prefix="/api/ea", tags=["EA Bridge"])
app.include_router(users.router, prefix="/users", tags=["Users"])
app.include_router(bots.router, prefix="/bots", tags=["Bots"])
app.include_router(trades.router, prefix="/trades", tags=["Trades"])
app.include_router(positions.router, prefix="/positions", tags=["Positions"])
app.include_router(billing.router, prefix="/billing", tags=["Billing"])
app.include_router(admin.router, prefix="/admin", tags=["Admin"])

import asyncio
import os
import sentry_sdk
from prometheus_client import make_asgi_app

from app.services.metaapi_service import cache_all_account_statuses

# Initialize Sentry for error tracking
sentry_dsn = os.getenv("SENTRY_DSN")
if sentry_dsn:
    sentry_sdk.init(
        dsn=sentry_dsn,
        traces_sample_rate=1.0,
        profiles_sample_rate=1.0,
    )

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(cache_all_account_statuses())

@app.get("/health")
def health_check():
    return {"status": "running", "version": "1.0.0"}

# Mount the Prometheus metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)
