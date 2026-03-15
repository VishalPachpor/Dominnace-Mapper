import json
import hashlib
import logging
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.models.bot import Bot, UserBot
from app.utils.redis_client import redis_client
from app.utils.metrics import (
    signals_received_total,
    signals_routed_total,
    signals_dropped_total,
    idempotency_drops_total
)

from app.utils.telegram import send_telegram_message

QUEUE_NAME = "signal_queue"

async def route_signal(data: dict, db: Session):
    """
    Decoupled signal routing. Retrieves the specific bot via its slug,
    finds all actively subscribed users, and fans out Individual trades
    to the Redis queue for the execution engine worker to process.
    """
    # ── Critical Protection 1: Idempotency ──
    # Create a SHA256 hash of the payload to prevent TradingView webhook retry duplicates
    raw_payload_str = json.dumps(data, sort_keys=True)
    signal_hash = hashlib.sha256(raw_payload_str.encode()).hexdigest()
    
    # If this exact signal payload was processed in the last 60 seconds, ignore it
    if redis_client.get(f"signal_processed:{signal_hash}"):
        logger.info(f"[Router] Duplicate signal detected and dropped: {signal_hash}")
        signals_dropped_total.labels(reason="idempotency_match").inc()
        return 0
        
    # Mark signal as processed (expiry 60 seconds)
    redis_client.setex(f"signal_processed:{signal_hash}", 60, "1")

    # ── Bot Lookup ──
    # Priority 1: Explicit "bot" slug in payload (most reliable — add to TradingView alert)
    # Priority 2: Signal type alias map (DOM → dm-bull, SMC → smc-buy, etc.)
    # Priority 3: Exact slug match on signal_type
    # Priority 4: Partial name contains signal_type
    SIGNAL_TYPE_MAP = {
        "dom": "dm-bull",
        "dominance": "dm-bull",
        "smc": "smc-buy",
        "breakout": "breakout-pro",
    }

    bot_slug = data.get("bot")
    signal_type = str(data.get("signal_type", "")).lower()

    if bot_slug:
        bot = db.query(Bot).filter(Bot.slug == bot_slug, Bot.is_active == True).first()
        if not bot:
            logger.warning(f"[Router] No active bot found for slug '{bot_slug}'")
            signals_dropped_total.labels(reason="inactive_bot").inc()
            return 0
    elif signal_type:
        # Try alias map first (DOM → dm-bull), then exact slug, then name contains
        resolved_slug = SIGNAL_TYPE_MAP.get(signal_type)
        if resolved_slug:
            bot = db.query(Bot).filter(Bot.slug == resolved_slug, Bot.is_active == True).first()
            logger.info(f"[Router] Resolved signal_type '{signal_type}' → slug '{resolved_slug}'")
        else:
            bot = (
                db.query(Bot).filter(Bot.slug == signal_type, Bot.is_active == True).first()
                or db.query(Bot).filter(Bot.name.ilike(f"%{signal_type}%"), Bot.is_active == True).first()
            )
        if not bot:
            logger.warning(
                f"[Router] No active bot found for signal_type '{signal_type}'. "
                f"Known aliases: {list(SIGNAL_TYPE_MAP.keys())}. "
                f"Or add '\"bot\": \"<your-bot-slug>\"' directly to your TradingView alert."
            )
            signals_dropped_total.labels(reason="inactive_bot").inc()
            return 0
    else:
        logger.warning("[Router] Signal has neither 'bot' nor 'signal_type' field")
        signals_dropped_total.labels(reason="missing_bot_slug").inc()
        return 0

    signals_received_total.labels(bot=bot.slug).inc()

    # ── Option B: Global Signal Broadcast ──
    # Broadcast to Telegram immediately after bot validation
    symbol = data.get("symbol", "UNKNOWN")
    action = str(data.get("action", "signal")).upper()
    price = data.get("price", "N/A")
    
    broadcast_msg = (
        f"📢 <b>{bot.name} Signal Alert</b>\n\n"
        f"<b>Symbol:</b> {symbol}\n"
        f"<b>Action:</b> {action}\n"
        f"<b>Price:</b> {price}\n"
        f"<b>Format:</b> {signal_type.upper()}\n\n"
        f"<i>Processing execution for connected subscribers...</i>"
    )
    await send_telegram_message(broadcast_msg)

    # Get active subscribers for this bot
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
        logger.info(f"[Router] Bot '{bot.name}' fanned out to 0 active connected users.")
        signals_dropped_total.labels(reason="no_active_subscribers").inc()
        return 0

    routed_count = 0
    for user_bot in enrolled_users:
        task_payload = {
            "user_id": str(user_bot.user_id),
            "bot_id": str(bot.id),
            "bot_name": bot.name,
            "symbol": symbol,
            "side": data.get("action") or data.get("side"),
            "type": data.get("type", "MARKET"),
            "price": price,
            "sl": data.get("sl"),
            "tp": data.get("tp"),
            "custom_lot_size": user_bot.custom_lot_size,
            "max_bot_lot_size": bot.max_lot_size
        }
        
        merged_payload = {**data, **task_payload}
        redis_client.lpush(QUEUE_NAME, json.dumps(merged_payload))
        routed_count += 1
        
    signals_routed_total.labels(bot=bot.slug).inc(routed_count)
    logger.info(f"[Router] Fanned out '{bot.name}' signal to {routed_count} users.")
    return routed_count
