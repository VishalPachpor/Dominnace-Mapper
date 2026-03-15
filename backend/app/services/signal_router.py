import json
import hashlib
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.bot import Bot, UserBot
from app.utils.redis_client import redis_client
from app.utils.metrics import (
    signals_received_total,
    signals_routed_total,
    signals_dropped_total,
    idempotency_drops_total
)

QUEUE_NAME = "signal_queue"

def route_signal(data: dict, db: Session):
    """
    Decoupled signal routing. Retrieves the specific bot via its slug,
    finds all actively subscribed users, and fans out Individual trades
    to the Redis queue for the execution engine worker to process.
    """
    bot_slug = data.get("bot", "UNKNOWN")
    signals_received_total.labels(bot=bot_slug).inc()

    # ── Critical Protection 1: Idempotency ──
    # Create a SHA256 hash of the payload to prevent TradingView webhook retry duplicates
    raw_payload_str = json.dumps(data, sort_keys=True)
    signal_hash = hashlib.sha256(raw_payload_str.encode()).hexdigest()
    
    # If this exact signal payload was processed in the last 60 seconds, ignore it
    if redis_client.get(f"signal_processed:{signal_hash}"):
        print(f"[Router] Duplicate signal detected and dropped: {signal_hash}")
        idempotency_drops_total.labels(bot=bot_slug).inc()
        signals_dropped_total.labels(reason="idempotency_match").inc()
        return 0
        
    # Mark signal as processed (expiry 60 seconds)
    redis_client.setex(f"signal_processed:{signal_hash}", 60, "1")

    if bot_slug == "UNKNOWN":
        # Fallback or strict error. Let's assume strict.
        signals_dropped_total.labels(reason="missing_bot_slug").inc()
        raise HTTPException(status_code=400, detail="Missing 'bot' identifier in signal payload")
    
    bot = db.query(Bot).filter(Bot.slug == bot_slug, Bot.is_active == True).first()
    if not bot:
        # Ignore unrecognised inactive bots
        print(f"[Router] Ignored signal for inactive or unknown bot: {bot_slug}")
        signals_dropped_total.labels(reason="inactive_bot").inc()
        return 0

    # Get active subscribers for this bot whose trading is not paused AND who are actually connected
    from app.models.user import User
    from sqlalchemy import or_

    enrolled_users = db.query(UserBot).join(User, User.id == UserBot.user_id).filter(
        UserBot.bot_id == bot.id,
        UserBot.is_enabled == True,
        User.trading_paused == False,
        or_(
            User.mt_status == "connected",
            User.ea_token.isnot(None)
        )
    ).all()
    
    if not enrolled_users:
        signals_dropped_total.labels(reason="no_active_subscribers").inc()

    routed_count = 0
    for user_bot in enrolled_users:
        # Create a user-specific task payload
        task_payload = {
            "user_id": str(user_bot.user_id),
            "bot_id": str(bot.id),
            "bot_name": bot.name,
            "symbol": data.get("symbol"),
            "side": data.get("side"),
            "type": data.get("type", "MARKET"),
            "price": data.get("price"),
            "sl": data.get("sl"),
            "tp": data.get("tp"),
            # Merge in max lot constraints or custom overrides
            "custom_lot_size": user_bot.custom_lot_size,
            "max_bot_lot_size": bot.max_lot_size
        }
        
        # Merge any other arbitrary payload metadata 
        # (e.g. from TradingView alert like Timeframe)
        merged_payload = {**data, **task_payload}
        
        redis_client.lpush(QUEUE_NAME, json.dumps(merged_payload))
        routed_count += 1
        
    signals_routed_total.labels(bot=bot.slug).inc(routed_count)
    print(f"[Router] Fanned out '{bot.name}' signal to {routed_count} users.")
    return routed_count
