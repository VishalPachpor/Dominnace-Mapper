"""
Broker-Aware Execution Adapter

Converts raw signal → broker-compliant MT5 order payload.
Runs BEFORE any MetaApi call is made.

Execution Flow:
    1. Fetch symbol specification from MetaApi (cached 10 min)
    2. Fetch account info for margin check (cached 30s)
    3. Resolve symbol: BTCUSDT → BTCUSDm etc.
    4. Normalize volume: clamp to minVolume + round to volumeStep
    5. Calculate minimum stop distance: stopLevel × point
    6. Normalize SL/TP: expand if inside stopLevel, apply spread buffer
    7. Apply precision rounding (broker`s digits field)
    8. Validate margin sufficiency
    9. Pre-validate final payload
    10. Return clean order dict OR raise ExecutionValidationError

Execution Modes:
    SAFE   → If SL/TP still invalid after normalization, strip them and execute
    STRICT → Raise ExecutionValidationError if SL/TP cannot be made valid
"""

import logging
import json
from typing import Optional
from app.services.exceptions import ExecutionValidationError, BrokerAdapterError
from app.services.symbol_mapper import resolve_symbol

logger = logging.getLogger(__name__)

# ─── Execution Mode ────────────────────────────────────────────────────────────
# SAFE:   If stops can't be made valid, remove them and execute without stops.
# STRICT: Raise ExecutionValidationError("INVALID_SL" / "INVALID_TP") instead.
EXECUTION_MODE = "SAFE"

# Safety cap — never execute more than this lot size regardless of signal
GLOBAL_MAX_VOLUME = 0.10


# ─── Step 1: Volume Normalization ─────────────────────────────────────────────

def normalize_volume(requested_volume: float, symbol_info: dict) -> float:
    """
    Clamps volume to broker minVolume and rounds to volumeStep.

    Example:
        requested=0.003, minVolume=0.01, step=0.01 → returns 0.01
        requested=0.025, minVolume=0.01, step=0.01 → returns 0.02 (floor to step)
    """
    min_vol = float(symbol_info.get("minVolume", 0.01))
    max_vol = float(symbol_info.get("maxVolume", GLOBAL_MAX_VOLUME))
    step = float(symbol_info.get("volumeStep", 0.01))

    # Clamp volume to [minVolume, GLOBAL_MAX_VOLUME]
    volume = max(requested_volume, min_vol)
    volume = min(volume, min(max_vol, GLOBAL_MAX_VOLUME))

    # Round down to nearest step
    volume = int(volume / step) * step
    volume = round(volume, 10)  # floating point cleanup

    # Final safety: ensure still >= minVolume after step rounding
    volume = max(volume, min_vol)

    logger.debug(f"[Adapter] Volume: requested={requested_volume} → normalized={volume} (min={min_vol}, step={step})")
    return volume


# ─── Step 2: Price Precision ───────────────────────────────────────────────────

def normalize_price(price: Optional[float], symbol_info: dict) -> Optional[float]:
    """
    Rounds price to broker`s digit precision.
    Some brokers reject orders with precision mismatches.
    """
    if price is None:
        return None
    digits = int(symbol_info.get("digits", 5))
    rounded = round(price, digits)
    return rounded


# ─── Step 3: Minimum Stop Distance ────────────────────────────────────────────

def get_min_stop_distance(symbol_info: dict) -> float:
    """
    Returns the minimum pip distance required for SL/TP from entry.
    Formula: stopLevel (in points) × point size
    """
    stop_level = float(symbol_info.get("stopLevel", 0))
    point = float(symbol_info.get("point", 0.00001))
    return stop_level * point


# ─── Step 4: Spread Buffer ────────────────────────────────────────────────────

def get_spread(symbol_info: dict) -> float:
    """
    Returns the current broker spread in price units.
    Falls back to 0 if not provided (spread-awareness is a bonus, not required).
    """
    return float(symbol_info.get("spread", 0)) * float(symbol_info.get("point", 0.00001))


# ─── Step 5: SL/TP Normalization ──────────────────────────────────────────────

def normalize_stops(
    entry: float,
    sl: Optional[float],
    tp: Optional[float],
    min_distance: float,
    spread: float,
    side: str,
    symbol_info: dict,
) -> tuple[Optional[float], Optional[float], bool]:
    """
    Adjusts SL/TP to satisfy broker`s minimum stop distance + spread buffer.

    Returns:
        (sl, tp, stops_were_adjusted) — stops_were_adjusted=True means we had to change them.

    For BUY:
        SL must be < entry - min_distance
        TP must be > entry + min_distance
    For SELL:
        SL must be > entry + min_distance
        TP must be < entry - min_distance
    """
    stops_adjusted = False
    spread_buffer = spread * 0.5  # add half-spread buffer on top of min_distance
    total_distance = min_distance + spread_buffer

    if side.upper() == "BUY":
        if sl is not None:
            required_sl = entry - total_distance
            if (entry - sl) < total_distance:
                logger.info(f"[Adapter] BUY SL too close ({sl:.5f} vs entry {entry:.5f}). Adjusting to {required_sl * 1.2:.5f}")
                sl = entry - (total_distance * 1.2)
                stops_adjusted = True

        if tp is not None:
            required_tp = entry + total_distance
            if (tp - entry) < total_distance:
                logger.info(f"[Adapter] BUY TP too close ({tp:.5f} vs entry {entry:.5f}). Adjusting to {required_tp * 1.5:.5f}")
                tp = entry + (total_distance * 1.5)
                stops_adjusted = True

    else:  # SELL
        if sl is not None:
            required_sl = entry + total_distance
            if (sl - entry) < total_distance:
                logger.info(f"[Adapter] SELL SL too close ({sl:.5f} vs entry {entry:.5f}). Adjusting to {required_sl * 1.2:.5f}")
                sl = entry + (total_distance * 1.2)
                stops_adjusted = True

        if tp is not None:
            required_tp = entry - total_distance
            if (entry - tp) < total_distance:
                logger.info(f"[Adapter] SELL TP too close ({tp:.5f} vs entry {entry:.5f}). Adjusting to {required_tp * 1.5:.5f}")
                tp = entry - (total_distance * 1.5)
                stops_adjusted = True

    # Final precision round
    digits = int(symbol_info.get("digits", 5))
    sl = round(sl, digits) if sl is not None else None
    tp = round(tp, digits) if tp is not None else None

    return sl, tp, stops_adjusted


# ─── Step 6: Pre-Trade Validation ─────────────────────────────────────────────

def validate_order(order: dict, symbol_info: dict, min_distance: float):
    """
    Final sanity check BEFORE sending to MT5.
    Raises ExecutionValidationError with specific codes for each failure.
    """
    min_vol = float(symbol_info.get("minVolume", 0.01))
    if order["volume"] < min_vol:
        raise ExecutionValidationError(
            "INVALID_VOLUME",
            f"Volume {order['volume']} is below broker minimum {min_vol}"
        )

    entry = float(order.get("entry") or order.get("price") or 0)
    sl = order.get("sl")
    tp = order.get("tp")
    side = order.get("side", "BUY").upper()

    if entry:
        if side == "BUY":
            if sl and sl >= entry - min_distance:
                raise ExecutionValidationError("INVALID_SL", f"BUY SL {sl} must be < {entry - min_distance}")
            if tp and tp <= entry + min_distance:
                raise ExecutionValidationError("INVALID_TP", f"BUY TP {tp} must be > {entry + min_distance}")
        else: # SELL
            if sl and sl <= entry + min_distance:
                raise ExecutionValidationError("INVALID_SL", f"SELL SL {sl} must be > {entry + min_distance}")
            if tp and tp >= entry - min_distance:
                raise ExecutionValidationError("INVALID_TP", f"SELL TP {tp} must be < {entry - min_distance}")


# ─── MAIN ADAPTER FUNCTION ────────────────────────────────────────────────────

async def adapt_order(signal: dict, account_id: str) -> dict:
    """
    The single entry point for all trade adaptation logic.

    Args:
        signal:     Raw merged signal payload from the Redis queue.
        account_id: MetaApi Terminal account ID for the connected MT5 user.

    Returns:
        A clean, broker-safe order dictionary ready for MetaApi execution.

    Raises:
        ExecutionValidationError: Pre-broker validation failed. Log and stop.
        BrokerAdapterError:       Could not fetch broker spec. Retry may help.
    """
    from app.services.metaapi_service import (
        get_symbol_specification,
        get_account_information,
        get_open_positions,
    )

    symbol_raw = signal.get("symbol", "")
    side = str(signal.get("side") or signal.get("action") or "BUY").upper()
    order_type = str(signal.get("type", "MARKET")).upper()

    # ── Stage 1: Fetch symbol specification (cached) ──────────────────────────
    logger.info(f"[Adapter] Fetching symbol spec for {symbol_raw} on {account_id}")
    symbol_info = await get_symbol_specification(account_id, symbol_raw)

    if not symbol_info:
        raise BrokerAdapterError(f"Could not fetch symbol specification for '{symbol_raw}' from MetaApi")

    # ── Stage 2: Symbol resolution ────────────────────────────────────────────
    try:
        account_symbols = [s["symbol"] for s in (symbol_info.get("_all_symbols") or [])]
        if not account_symbols:
            # Fall back: use the spec we already have, its symbol key is the resolved name
            broker_symbol = symbol_info.get("symbol", symbol_raw)
        else:
            broker_symbol = resolve_symbol(symbol_raw, account_symbols)
    except ExecutionValidationError:
        # Re-raise SYMBOL_NOT_SUPPORTED with clean stage label
        raise ExecutionValidationError(
            "SYMBOL_NOT_SUPPORTED",
            f"Symbol '{symbol_raw}' is not available on broker account {account_id}"
        )

    logger.info(f"[Adapter] Symbol resolved: {symbol_raw} → {broker_symbol}")

    # ── Stage 3: Volume normalization ─────────────────────────────────────────
    requested_volume = float(signal.get("custom_lot_size") or signal.get("max_bot_lot_size") or 0.01)
    volume = normalize_volume(requested_volume, symbol_info)

    # ── Stage 4: Stop distance calculation ───────────────────────────────────
    min_distance = get_min_stop_distance(symbol_info)
    spread = get_spread(symbol_info)
    logger.info(f"[Adapter] min_distance={min_distance:.5f}, spread={spread:.5f}")

    # ── Stage 5: Entry price ──────────────────────────────────────────────────
    raw_entry = signal.get("price") or signal.get("entry")
    try:
        entry = float(raw_entry) if raw_entry else None
    except (TypeError, ValueError):
        entry = None

    # For MARKET orders, price is None (broker uses current market price)
    order_price = None if order_type == "MARKET" else normalize_price(entry, symbol_info)

    # ── Stage 6: SL/TP normalization ──────────────────────────────────────────
    raw_sl = signal.get("sl")
    raw_tp = signal.get("tp")
    sl = float(raw_sl) if raw_sl else None
    tp = float(raw_tp) if raw_tp else None

    stops_adjusted = False
    if sl is not None or tp is not None:
        if entry:
            try:
                sl, tp, stops_adjusted = normalize_stops(
                    entry=entry,
                    sl=sl,
                    tp=tp,
                    min_distance=min_distance,
                    spread=spread,
                    side=side,
                    symbol_info=symbol_info,
                )
            except Exception as e:
                logger.warning(f"[Adapter] Stop normalization failed: {e}. Applying EXECUTION_MODE={EXECUTION_MODE}")
                if EXECUTION_MODE == "SAFE":
                    sl = None
                    tp = None
                    stops_adjusted = True
                else:
                    raise ExecutionValidationError("INVALID_STOPS", str(e))

    # ── Stage 7: Margin pre-check ──────────────────────────────────────────────
    try:
        account_info = await get_account_information(account_id)
        free_margin = account_info.get("freeMargin", account_info.get("margin", 0))
        if free_margin is not None and free_margin < 10:
            raise ExecutionValidationError(
                "INSUFFICIENT_MARGIN",
                f"Insufficient free margin: ${free_margin:.2f}. Cannot open new position."
            )
    except ExecutionValidationError:
        raise
    except Exception as e:
        # Don't block execution if margin check itself fails
        logger.warning(f"[Adapter] Margin check failed (non-blocking): {e}")

    # ── Stage 8: Build final validated order ──────────────────────────────────
    order = {
        "symbol": broker_symbol,
        "side": side,
        "type": order_type,
        "volume": volume,
        "price": order_price,      # None for MARKET orders
        "sl": sl,
        "tp": tp,
        "entry": entry,           # original entry for latency tracking
        "_stops_adjusted": stops_adjusted,
        "_original_symbol": symbol_raw,
    }

    # ── Stage 9: Final pre-validation ─────────────────────────────────────────
    if EXECUTION_MODE == "STRICT":
        validate_order(order, symbol_info, min_distance)
    else:
        try:
            validate_order(order, symbol_info, min_distance)
        except ExecutionValidationError as e:
            logger.warning(f"[Adapter] SAFE mode: pre-validation failed ({e.code}). Stripping stops and proceeding.")
            order["sl"] = None
            order["tp"] = None
            order["_stops_adjusted"] = True
            order["_execution_note"] = f"Stops removed in SAFE mode due to broker constraints: {e.message}"

    logger.info(
        f"[Adapter] ✅ Order adapted: symbol={broker_symbol}, side={side}, "
        f"volume={volume}, sl={sl}, tp={tp}, stops_adjusted={stops_adjusted}"
    )
    return order
