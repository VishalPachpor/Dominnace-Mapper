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

# ── Bot Alias Maps ──
# BOT_ALIAS_MAP: Normalizes incoming "bot" slugs from TradingView to actual DB slugs.
# Add entries here when the TradingView alert uses a different name than your DB slug.
BOT_ALIAS_MAP = {
    "dominance_crypto": "dm-bull",
    "dm_bull": "dm-bull",
    "dm-bear": "dm-bull",
}

# SIGNAL_TYPE_MAP: Resolves signal_type field to bot slugs (fallback when "bot" field is missing).
SIGNAL_TYPE_MAP = {
    "dom": "dm-bull",
    "dominance": "dm-bull",
    "smc": "smc-buy",
    "breakout": "breakout-pro",
    "gold": "dominance_gold",
    "xauusd": "dominance_gold",
}


def _log_signal_failure(db: Session, reason: str, data: dict, incoming_slug: str = None):
    """
    Persists every dropped signal to DB so we never have silent drops.
    """
    try:
        from app.models.signal_failure import SignalFailure
        failure = SignalFailure(
            reason=reason,
            incoming_slug=incoming_slug or data.get("bot") or data.get("signal_type"),
            symbol=data.get("symbol"),
            direction=str(data.get("action") or data.get("side") or "").upper() or None,
            raw_payload=data,
        )
        db.add(failure)
        db.commit()
    except Exception as e:
        logger.error(f"[Router] Failed to log signal failure: {e}")


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
        _log_signal_failure(db, "IDEMPOTENCY_DUPLICATE", data)
        return 0
        
    # Mark signal as processed (expiry 60 seconds)
    redis_client.setex(f"signal_processed:{signal_hash}", 60, "1")

    # ── Bot Lookup ──
    # Priority 1: Explicit "bot" slug in payload (most reliable)
    #   → First check BOT_ALIAS_MAP to normalize legacy/alternative slugs
    # Priority 2: Signal type alias map (DOM → dominance_crypto, etc.)
    # Priority 3: Exact slug match on signal_type
    # Priority 4: Partial name contains signal_type

    bot_slug = data.get("bot")
    signal_type = str(data.get("signal_type", "")).lower()

    if bot_slug:
        # Normalize via alias map (dm-bull → dominance_crypto)
        resolved_slug = BOT_ALIAS_MAP.get(bot_slug, bot_slug)
        if resolved_slug != bot_slug:
            logger.info(f"[Router] Alias resolved: '{bot_slug}' → '{resolved_slug}'")

        bot = db.query(Bot).filter(Bot.slug == resolved_slug, Bot.is_active == True).first()
        if not bot:
            logger.warning(f"[Router] No active bot found for slug '{bot_slug}' (resolved: '{resolved_slug}')")
            signals_dropped_total.labels(reason="bot_not_found").inc()
            _log_signal_failure(db, "BOT_NOT_FOUND", data, bot_slug)
            await send_telegram_message(
                f"⚠️ <b>Signal Dropped</b>\n\n"
                f"<b>Reason:</b> Bot not found\n"
                f"<b>Slug:</b> {bot_slug} → {resolved_slug}\n"
                f"<b>Symbol:</b> {data.get('symbol', 'N/A')}\n"
                f"<b>Action:</b> {data.get('action', 'N/A')}\n\n"
                f"<i>Add this slug to BOT_ALIAS_MAP or create the bot in DB</i>"
            )
            return 0
    elif signal_type:
        # Try alias map first (DOM → dominance_crypto), then exact slug, then name contains
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
            signals_dropped_total.labels(reason="bot_not_found").inc()
            _log_signal_failure(db, "BOT_NOT_FOUND", data, signal_type)
            await send_telegram_message(
                f"⚠️ <b>Signal Dropped</b>\n\n"
                f"<b>Reason:</b> Signal type not mapped\n"
                f"<b>Type:</b> {signal_type}\n"
                f"<b>Symbol:</b> {data.get('symbol', 'N/A')}\n\n"
                f"<i>Add this type to SIGNAL_TYPE_MAP</i>"
            )
            return 0
    else:
        logger.warning("[Router] Signal has neither 'bot' nor 'signal_type' field")
        signals_dropped_total.labels(reason="missing_bot_slug").inc()
        _log_signal_failure(db, "MISSING_BOT_SLUG", data)
        await send_telegram_message(
            f"⚠️ <b>Signal Dropped</b>\n\n"
            f"<b>Reason:</b> No bot or signal_type in payload\n"
            f"<b>Symbol:</b> {data.get('symbol', 'N/A')}\n\n"
            f"<i>Check TradingView alert format</i>"
        )
        return 0

    signals_received_total.labels(bot=bot.slug).inc()
    
    symbol = data.get("symbol", "UNKNOWN")
    action = str(data.get("action") or data.get("side") or "signal").upper()
    raw_price = data.get("price", "N/A")

    # ── 1. Create Signal Record ──
    from app.models.signal import Signal
    from datetime import datetime, timezone

    time_str = data.get("time")
    if time_str:
        try:
            signal_time = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
        except Exception:
            signal_time = datetime.now(timezone.utc)
    else:
        signal_time = datetime.now(timezone.utc)

    try:
        price_val = float(raw_price)
    except (TypeError, ValueError):
        price_val = None

    signal_obj = Signal(
        bot_id=str(bot.id),
        symbol=symbol,
        direction=action,
        signal_time=signal_time,
        price_at_signal=price_val,
        raw_payload=data
    )
    db.add(signal_obj)
    db.commit()
    db.refresh(signal_obj)

    # ── Option B: Global Signal Broadcast ──
    # Broadcast to Telegram immediately after bot validation
    
    broadcast_msg = (
        f"📢 <b>{bot.name} Signal Alert</b>\n\n"
        f"<b>Symbol:</b> {symbol}\n"
        f"<b>Action:</b> {action}\n"
        f"<b>Price:</b> {raw_price}\n"
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
        _log_signal_failure(db, "NO_ACTIVE_SUBSCRIBERS", data, bot.slug)
        return 0

    routed_count = 0
    for user_bot in enrolled_users:
        task_payload = {
            "signal_id": str(signal_obj.id),
            "signal_time": signal_time.isoformat(),
            "user_id": str(user_bot.user_id),
            "bot_id": str(bot.id),
            "bot_name": bot.name,
            "symbol": symbol,
            "side": action,
            "type": data.get("type", "MARKET"),
            "price": raw_price,
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
