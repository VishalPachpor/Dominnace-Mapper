import json
from fastapi import APIRouter, Request, HTTPException
from app.config import WEBHOOK_SECRET
from app.utils.redis_client import redis_client

router = APIRouter()

QUEUE_NAME = "signal_queue"

@router.post("/webhook")
async def receive_signal(request: Request):
    data = await request.json()

    if data.get("secret") != WEBHOOK_SECRET:
        raise HTTPException(403, "Invalid secret")

    # Critical Fix #1 — use consistent queue name and json.dumps instead of str()
    redis_client.lpush(QUEUE_NAME, json.dumps(data))

    return {"status": "signal queued"}
