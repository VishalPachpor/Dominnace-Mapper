from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.orm import Session
from app.config import WEBHOOK_SECRET
from app.database.db import get_db
from app.services.signal_router import route_signal
from app.utils.metrics import webhook_requests_total, webhook_latency_seconds, webhook_errors_total

router = APIRouter()

@router.post("/webhook")
async def receive_signal(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    symbol = data.get("symbol", "UNKNOWN")

    # Increment request counter
    webhook_requests_total.labels(symbol=symbol).inc()

    # Track processing latency
    with webhook_latency_seconds.labels(symbol=symbol).time():
        if data.get("secret") != WEBHOOK_SECRET:
            webhook_errors_total.labels(error_type="invalid_secret").inc()
            raise HTTPException(403, "Invalid secret")

        # Delegate to the newly architected fan-out Bot Management routing layer
        routed_count = route_signal(data, db)

    return {"status": "signal queued", "routed_to_users": routed_count}
