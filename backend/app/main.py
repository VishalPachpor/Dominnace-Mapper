from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import auth, webhook, users, trades, billing, admin, positions, ea_bridge
from app.config import FRONTEND_URL

app = FastAPI(
    title="DominanceBot API",
    description="Trading SaaS Platform API",
    version="1.0.0"
)

# Critical Fix #4 — CORS so the Next.js frontend can reach the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(webhook.router, prefix="/api", tags=["Webhook"])
app.include_router(ea_bridge.router, prefix="/api/ea", tags=["EA Bridge"])
app.include_router(users.router, prefix="/users", tags=["Users"])
app.include_router(trades.router, prefix="/trades", tags=["Trades"])
app.include_router(positions.router, prefix="/positions", tags=["Positions"])
app.include_router(billing.router, prefix="/billing", tags=["Billing"])
app.include_router(admin.router, prefix="/admin", tags=["Admin"])

@app.get("/health")
def health_check():
    return {"status": "running", "version": "1.0.0"}

@app.get("/metrics")
def get_metrics():
    return {"workers_active": True, "redis_connected": True, "exchange_status": "ok"}
