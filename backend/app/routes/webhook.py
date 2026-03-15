"""
TradingView Webhook Endpoint

Critical design decisions:
1. ALWAYS respond within 200ms — TradingView has a 5-second timeout.
   We fan-out the signal via signal_router (DB lookup) in a background thread,
   then each user-specific task goes to Redis for the worker to execute.
2. The secret check is the only thing done inline — it's a fast dict lookup.
3. All heavy lifting (DB queries, MetaApi calls) is in the background/worker.
"""
import logging
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.config import WEBHOOK_SECRET
from app.database.db import SessionLocal
from app.utils.metrics import webhook_requests_total, webhook_errors_total
from app.services.signal_router import route_signal

logger = logging.getLogger(__name__)
router = APIRouter()


def _fanout_signal(data: dict):
    """
    Runs in a background thread after we've already returned 200 to TradingView.
    Opens a DB session, calls signal_router to fan-out the signal to subscribed users,
    and pushes one Redis task per user.
    """
    db: Session = SessionLocal()
    try:
        routed_count = route_signal(data, db)
        logger.info(f"[Webhook] Signal fanned out to {routed_count} users: "
                    f"symbol={data.get('symbol')} action={data.get('action')}")
    except Exception as e:
        logger.error(f"[Webhook] Error during signal fan-out: {e}")
    finally:
        db.close()


@router.post("/webhook")
async def receive_signal(request: Request, background_tasks: BackgroundTasks):
    """
    Ingests a TradingView alert and IMMEDIATELY returns 200 OK.
    The fan-out to subscribed users happens asynchronously in a background task.

    TradingView alert message format (paste this into your alert):
    {
        "secret": "superwebhooksecret",
        "bot": "dm-bull",
        "symbol": "{{ticker}}",
        "action": "buy",
        "price": {{close}},
        "dom_high": {{high}},
        "dom_low": {{low}},
        "signal_type": "DOM"
    }

    The "bot" field must match a Bot.slug in your database.
    """
    try:
        data = await request.json()
    except Exception:
        webhook_errors_total.labels(error_type="invalid_json").inc()
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    symbol = data.get("symbol", "UNKNOWN")
    webhook_requests_total.labels(symbol=symbol).inc()

    # ── Secret validation (fast — always inline) ──
    if data.get("secret") != WEBHOOK_SECRET:
        webhook_errors_total.labels(error_type="invalid_secret").inc()
        logger.warning(f"[Webhook] Rejected signal — invalid secret")
        raise HTTPException(status_code=403, detail="Invalid secret")

    # ── Fan-out runs in background — TradingView gets 200 instantly ──
    background_tasks.add_task(_fanout_signal, data)

    logger.info(f"[Webhook] Accepted: symbol={symbol} action={data.get('action')} bot={data.get('bot')}")
    return {"status": "queued", "symbol": symbol}
