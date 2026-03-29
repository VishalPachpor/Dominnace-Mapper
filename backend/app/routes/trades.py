from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.utils.subscription_check import check_subscription_active
from app.models.user import User
from app.models.trade import Trade
from app.models.position import Position
from app.models.trade_state import TradeState
from app.database.db import get_db
from app.utils.security import get_current_user
import ccxt
from typing import cast
import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

router = APIRouter()

def get_unified_trades(user_id: str, db: Session):
    """
    Normalizes legacy Trade records and modern Position records into a unified structure.
    """
    unified_trades = []
    state_rows = db.query(TradeState).filter(TradeState.user_id == user_id).all()
    state_by_position_id = {
        str(s.position_id): s
        for s in state_rows
        if s.position_id
    }

    def apply_state_authority(record_id: str, status: str, result: str | None):
        state = state_by_position_id.get(str(record_id))
        normalized_status = (status or "closed").lower()
        normalized_result = result

        if not state:
            return normalized_status, normalized_result

        state_status = (state.status or "").upper()
        if state_status in ["CLOSED", "REVERSED"]:
            normalized_status = "closed"
            if state_status == "REVERSED":
                normalized_result = normalized_result or "LOSS"
        elif state_status in ["OPEN", "BE_MOVED", "CLOSING"]:
            normalized_status = "open"
            normalized_result = "OPEN"

        return normalized_status, normalized_result

    legacy_trades = db.query(Trade).filter(Trade.user_id == user_id).all()
    trade_by_id = {str(t.id): t for t in legacy_trades}
    for t in legacy_trades:
        pnl = float(t.pnl or 0)
        result = t.result
        status = t.status or "closed"
        status, result = apply_state_authority(t.id, status, result)

        if not result and status.lower() in ["closed", "tp_hit", "stopped", "success"]:
            if pnl > 0:
                result = "WIN"
            elif pnl < 0:
                result = "LOSS"
            else:
                result = "BE"

        time_val = t.execution_time or t.created_at

        unified_trades.append({
            "id": t.id,
            "symbol": t.symbol,
            "side": t.side,
            "entry_price": t.entry,
            "exit_price": t.exit,
            "pnl": pnl,
            "result": result or "OPEN",
            "volume": t.lot_size or 0.01,
            "created_at": time_val, # For sorting
            "execution_time": t.execution_time.isoformat() if t.execution_time else None,
            "close_time": t.close_time.isoformat() if t.close_time else None,
            "execution_latency_ms": t.execution_latency_ms,
            "signal_time": t.signal.signal_time.isoformat() if hasattr(t, "signal") and t.signal and t.signal.signal_time else None,
            "status": status.lower(),
            "source": "database_trade",
            "reject_reason": getattr(t, "reject_reason", None)
        })

    # 2. Bot-executed positions from the 'positions' table
    # We want all positions to show in history, including OPEN
    bot_positions = db.query(Position).filter(
        Position.user_id == user_id,
        Position.status.in_(["success", "OPEN", "CLOSING", "CLOSED", "TP_HIT", "STOPPED"])
    ).all()

    for p in bot_positions:
        linked_trade = trade_by_id.get(str(p.id))
        canonical_entry = linked_trade.entry if linked_trade and linked_trade.entry is not None else p.entry
        canonical_exit = linked_trade.exit if linked_trade and linked_trade.exit is not None else p.exit_price
        canonical_pnl = (
            float(linked_trade.pnl)
            if linked_trade and linked_trade.pnl is not None
            else float(p.pnl or 0)
        )
        canonical_status = linked_trade.status if linked_trade and linked_trade.status else p.status
        canonical_result = linked_trade.result if linked_trade else None
        canonical_closed_at = (
            linked_trade.close_time
            if linked_trade and linked_trade.close_time is not None
            else p.closed_at
        )

        pnl = canonical_pnl
        status = (canonical_status or "open").lower()
        status, result = apply_state_authority(p.id, status, canonical_result)
        
        # Calculate WIN/LOSS/BE for closed positions
        if status == "open":
            result = "OPEN"
        elif status in ["closed", "tp_hit", "stopped", "success"]:
            status = "closed"
            if pnl > 0:
                result = "WIN"
            elif pnl < 0:
                result = "LOSS"
            else:
                result = result or "BE"

        # Use closed_at if available for chronological sorting, fallback to created_at
        time_val = canonical_closed_at if canonical_closed_at else p.created_at

        unified_trades.append({
            "id": p.id,
            "symbol": p.symbol,
            "side": p.side,
            "entry_price": canonical_entry,
            "exit_price": canonical_exit,
            "sl": p.sl,
            "tp": p.tp,
            "pnl": pnl,
            "closed_at": canonical_closed_at.isoformat() if canonical_closed_at else None,
            "result": result,
            "volume": (
                linked_trade.lot_size
                if linked_trade and linked_trade.lot_size is not None
                else (p.lot_size or 0.01)
            ),
            "created_at": time_val, # Keep as datetime object for sorting
            "status": status,
            "source": "bot_position",
            "reject_reason": None
        })
        
    # Sort chronologically (newest first for most lists, oldest first for equity curve)
    unified_trades.sort(key=lambda x: x["created_at"] if x["created_at"] else datetime.min, reverse=True)
    return unified_trades

@router.get("")
async def get_trades(user = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Returns all trades: unified DB trades + live open positions from MetaApi.
    """
    meta_account_id = getattr(user, "meta_account_id", None)

    # Reconcile stale DB-only OPEN rows against live broker positions before building history.
    # This keeps ghost rows out of History and prevents impossible close actions.
    if meta_account_id:
        try:
            from app.services.metaapi_service import get_open_positions
            from app.routes.positions import _finalize_stale_open_trade, _find_close_deal
            from app.services.metaapi_service import get_deal_history

            broker_positions = await get_open_positions(meta_account_id)
            broker_deals = await get_deal_history(meta_account_id)
            live_ids = {str(p.get("id")) for p in broker_positions if p.get("id") is not None}
            cutoff = datetime.now(timezone.utc) - timedelta(seconds=120)
            changed = False

            open_trades = db.query(Trade).filter(
                Trade.user_id == user.id,
                Trade.status.in_(["OPEN", "CLOSING"])
            ).all()
            for trade in open_trades:
                if str(trade.id) in live_ids:
                    continue
                opened_at = trade.execution_time or trade.created_at
                if opened_at and opened_at.tzinfo is None:
                    opened_at = opened_at.replace(tzinfo=timezone.utc)
                if opened_at and opened_at > cutoff:
                    continue
                _finalize_stale_open_trade(
                    db,
                    trade,
                    reason="BROKER_POSITION_NOT_FOUND",
                    close_deal=_find_close_deal(trade.id, broker_deals),
                )
                changed = True

            open_positions = db.query(Position).filter(
                Position.user_id == user.id,
                Position.status.in_(["OPEN", "CLOSING"])
            ).all()
            for pos in open_positions:
                if db.query(Trade.id).filter(Trade.id == pos.id).first():
                    # The linked trade row is authoritative and was handled above.
                    continue
                if str(pos.id) in live_ids:
                    continue
                opened_at = pos.created_at
                if opened_at and opened_at.tzinfo is None:
                    opened_at = opened_at.replace(tzinfo=timezone.utc)
                if opened_at and opened_at > cutoff:
                    continue
                # Orphaned position rows should not be finalized as fake
                # breakeven trades. Keep them in CLOSING until a real broker
                # close deal is found or a linked trade row reconciles them.
                pos.status = "CLOSING"
                state = db.query(TradeState).filter(TradeState.position_id == pos.id).first()
                if state and state.status in ("OPEN", "BE_MOVED", "CLOSING"):
                    state.status = "CLOSING"
                    state.last_checked_at = datetime.now(timezone.utc)
                changed = True

            if changed:
                db.commit()
        except Exception as e:
            logger.warning(f"Failed stale-history reconciliation for user {user.id}: {e}")

    unified_trades = get_unified_trades(user.id, db)
    
    # Format dates for API response
    result_list = []
    for t in unified_trades:
        formatted = dict(t)
        if formatted["created_at"]:
            formatted["created_at"] = formatted["created_at"].isoformat()
        result_list.append(formatted)

    # 2. Get LIVE data from MetaApi (Open Positions + Deal History)
    if meta_account_id:
        try:
            from app.services.metaapi_service import get_open_positions, get_deal_history
            
            # Fetch Live Open Positions
            positions = await get_open_positions(meta_account_id)
            existing_by_id = {str(r["id"]): r for r in result_list if r.get("id") is not None}
            live_ids = {str(p.get("id", "")) for p in positions if p.get("id") is not None}
            
            for p in positions:
                pos_id = str(p.get("id", ""))
                if pos_id in existing_by_id:
                    # MetaApi is source of truth for OPEN positions
                    row = existing_by_id[pos_id]
                    side_raw = p.get("type", "")
                    side = "buy" if "BUY" in side_raw.upper() else "sell"
                    row["status"] = "open"
                    row["result"] = "OPEN"
                    row["source"] = "metaapi_live"
                    row["symbol"] = row.get("symbol") or p.get("symbol", "")
                    row["side"] = row.get("side") or side
                    row["entry_price"] = row.get("entry_price") or p.get("openPrice", 0)
                    row["current_price"] = p.get("currentPrice", 0)
                    row["pnl"] = p.get("profit", row.get("pnl", 0))
                    continue
                side_raw = p.get("type", "")
                side = "buy" if "BUY" in side_raw.upper() else "sell"
                result_list.append({
                    "id": pos_id,
                    "symbol": p.get("symbol", ""),
                    "side": side,
                    "entry_price": p.get("openPrice", 0),
                    "exit_price": None,
                    "pnl": p.get("profit", 0),
                    "result": "OPEN",
                    "volume": p.get("volume", 0.01),
                    "created_at": p.get("time", None),
                    "status": "open",
                    "current_price": p.get("currentPrice", 0),
                    "source": "metaapi_live"
                })

            # Fetch Historical Deals (Closed Trades)
            deals = await get_deal_history(meta_account_id)
            
            # Map positionId -> entryPrice from DEAL_ENTRY_IN deals
            entry_map = {}
            for d in deals:
                if d.get("entryType") == "DEAL_ENTRY_IN":
                    pos_id = str(d.get("positionId", ""))
                    if pos_id:
                        entry_map[pos_id] = d.get("price")

            # Only include DEAL_ENTRY_OUT (closing deals) that aren't already in our result_list
            updated_existing_ids = {str(r["id"]) for r in result_list}
            
            for d in deals:
                if d.get("entryType") != "DEAL_ENTRY_OUT":
                    continue
                
                deal_id = str(d.get("id", ""))
                # MetaApi usually groups by positionId. If we have a positionId, use that to avoid duplicates.
                pos_id = str(d.get("positionId", deal_id))
                
                if pos_id in live_ids:
                    # Broker says it's still OPEN; never mark closed from history.
                    continue
                
                commission = float(d.get("commission", 0))
                swap = float(d.get("swap", 0))
                pnl = float(d.get("profit", 0)) + swap + commission
                side_raw = d.get("type", "")
                
                original_side = "sell" if "BUY" in side_raw.upper() else "buy"
                
                result = "BE"
                if pnl > 0: result = "WIN"
                elif pnl < 0: result = "LOSS"

                if pos_id in updated_existing_ids:
                    # Patch existing DB/open row with close info from broker history
                    row = existing_by_id.get(pos_id)
                    if row:
                        row["exit_price"] = d.get("price", 0)
                        row["pnl"] = round(pnl, 2)
                        row["result"] = result
                        row["status"] = "closed"
                        row["source"] = "metaapi_history"
                        row["commission"] = round(commission, 2)
                        row["swap"] = round(swap, 2)
                        row["deal_id"] = deal_id
                        row["broker_time"] = d.get("brokerTime")
                        row["close_time"] = d.get("time")
                        row["closed_at"] = d.get("time")
                        if not row.get("entry_price"):
                            row["entry_price"] = entry_map.get(pos_id)
                    continue

                if deal_id in updated_existing_ids:
                    continue

                result_list.append({
                    "id": pos_id, 
                    "symbol": d.get("symbol", ""),
                    "side": original_side,
                    "entry_price": entry_map.get(pos_id),
                    "exit_price": d.get("price", 0),
                    "pnl": round(pnl, 2),
                    "result": result,
                    "volume": d.get("volume", 0.01),
                    "created_at": d.get("time", None),
                    "status": "closed",
                    "source": "metaapi_history",
                    "commission": round(commission, 2),
                    "swap": round(swap, 2),
                    "deal_id": deal_id,
                    "broker_time": d.get("brokerTime")
                })

        except Exception as e:
            logger.error(f"Failed to fetch MetaApi data for trades list: {e}")

    # --- De-duplicate by id with a preference for OPEN + live broker records ---
    def _status_rank(status: str) -> int:
        s = (status or "").lower()
        return 2 if s == "open" else 1

    def _source_rank(source: str) -> int:
        src = source or ""
        # Prefer live broker data, then DB positions, then legacy trades, then broker history
        order = {
            "metaapi_live": 4,
            "bot_position": 3,
            "database_trade": 2,
            "metaapi_history": 1,
        }
        return order.get(src, 0)

    deduped = {}
    for row in result_list:
        rid = str(row.get("id", ""))
        if not rid:
            continue
        if rid not in deduped:
            deduped[rid] = row
            continue
        existing = deduped[rid]
        if (_status_rank(row.get("status")) > _status_rank(existing.get("status")) or
            (_status_rank(row.get("status")) == _status_rank(existing.get("status")) and
             _source_rank(row.get("source")) > _source_rank(existing.get("source")))):
            deduped[rid] = row

    # If we somehow dropped items with empty ids, re-add them.
    result_list = list(deduped.values()) + [r for r in result_list if not r.get("id")]

    # Re-sort everything chronologically newest first
    def parse_time(t_str):
        if not t_str: return datetime.min.replace(tzinfo=timezone.utc)
        if isinstance(t_str, datetime):
            if t_str.tzinfo is None:
                return t_str.replace(tzinfo=timezone.utc)
            return t_str
        try:
            val = datetime.fromisoformat(t_str.replace("Z", "+00:00"))
            if val.tzinfo is None:
                return val.replace(tzinfo=timezone.utc)
            return val
        except (ValueError, TypeError, AttributeError):
            return datetime.min.replace(tzinfo=timezone.utc)

    result_list.sort(key=lambda x: parse_time(x.get("created_at")), reverse=True)

    return result_list


@router.get("/dashboard")
async def get_dashboard_stats(user = Depends(get_current_user), db: Session = Depends(get_db)):
    current_balance = 10000.0
    current_equity = 10000.0
    active_trades_count = 0
    unrealized_pnl = 0.0
    daily_pnl = 0.0
    balance_fetched = False

    # A. Check EA Bridge MT5 Balance
    if getattr(user, "mt5_equity", 0.0) > 0:
        current_balance = getattr(user, "mt5_balance", current_balance)
        current_equity = user.mt5_equity
        unrealized_pnl = round(user.mt5_equity - getattr(user, "mt5_balance", 0.0), 2)
        active_trades_count = db.query(Position).filter(
            Position.user_id == user.id,
            Position.status.in_(["pending_ea", "picked_up", "executed", "OPEN"])
        ).count()
        balance_fetched = True
        logger.info(f"EA Bridge equity fetched: {current_equity} for user {user.id}")

    # B. MetaApi — use the cached service functions (same region, correct endpoints)
    elif getattr(user, "meta_account_id", None):
        try:
            from app.services.metaapi_service import get_account_information, get_open_positions
            acct = user.meta_account_id

            info = await get_account_information(acct)
            if info:
                current_balance = float(info.get("balance", current_balance))
                current_equity = float(info.get("equity", info.get("balance", current_equity)))
                balance_fetched = True

            positions = await get_open_positions(acct)
            active_trades_count = len(positions)
            unrealized_pnl = sum(float(p.get("profit", 0)) for p in positions)
        except Exception as e:
            logger.error(f"Failed to fetch MetaApi data for user {user.id}: {str(e)}")

    # Fallback to Binance if MetaApi not configured
    if not balance_fetched and user.exchange_api_key and user.exchange_secret_key:
        try:
            from app.utils.crypto_util import decrypt_password
            exchange = ccxt.binance({
                'apiKey': decrypt_password(user.exchange_api_key),
                'secret': decrypt_password(user.exchange_secret_key),
                'enableRateLimit': True,
                'options': {'defaultType': 'future'}
            })
            balance = exchange.fetch_balance()
            if 'USDT' in balance.get('total', {}):
                current_balance = float(balance['total']['USDT'])
                current_equity = current_balance
                balance_fetched = True
        except Exception as e:
            logger.error(f"Failed to fetch CCXT Binance balance for user {user.id}: {str(e)}")

    # --- Use Unified Trades for Stats ---
    unified_trades = get_unified_trades(user.id, db)
    closed_trades = [t for t in unified_trades if t["status"] == "closed"]
    
    # 2. Merge MetaApi History if available
    meta_account_id = getattr(user, "meta_account_id", None)
    if meta_account_id:
        try:
            from app.services.metaapi_service import get_deal_history
            deals = await get_deal_history(meta_account_id)
            existing_ids = {str(t["id"]) for t in closed_trades}
            
            for d in deals:
                if d.get("entryType") != "DEAL_ENTRY_OUT":
                    continue
                
                deal_id = str(d.get("id", ""))
                pos_id = str(d.get("positionId", deal_id))
                
                if pos_id in existing_ids or deal_id in existing_ids:
                    continue
                
                pnl = float(d.get("profit", 0)) + float(d.get("swap", 0)) + float(d.get("commission", 0))
                if pnl == 0: continue # Skip non-PnL deals if any
                
                result = "BE"
                if pnl > 0: result = "WIN"
                elif pnl < 0: result = "LOSS"
                
                closed_trades.append({
                    "id": pos_id,
                    "pnl": pnl,
                    "result": result
                })
        except Exception as e:
            logger.error(f"Failed to fetch MetaApi history for stats: {e}")

    realized_float = sum(t["pnl"] for t in closed_trades)
    unrealized_float = cast(float, unrealized_pnl)
    total_pnl = round(realized_float + unrealized_float, 2)

    # Win Rate (Ignoring Break Even trades)
    wins = len([t for t in closed_trades if t["result"] == "WIN"])
    losses = len([t for t in closed_trades if t["result"] == "LOSS"])
    total_for_winrate = wins + losses
    win_rate = (wins / total_for_winrate * 100) if total_for_winrate > 0 else 0

    # Profit Factor
    gross_profit = sum(t["pnl"] for t in closed_trades if t["pnl"] > 0)
    gross_loss = abs(sum(t["pnl"] for t in closed_trades if t["pnl"] < 0))
    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else None

    # 3. Equity curve — built from MetaApi deal history + live positions
    equity_data = []
    meta_account_id = getattr(user, "meta_account_id", None)

    if meta_account_id:
        try:
            from app.services.metaapi_service import get_deal_history, get_open_positions as get_pos
            from datetime import datetime
            
            today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

            deals = await get_deal_history(meta_account_id)
            live_positions = await get_pos(meta_account_id)
            
            # Calculate REAL Daily PnL directly from MetaApi closed deals today
            today_deals = [d for d in deals if d.get("time", "").startswith(today_str) and float(d.get("profit", 0)) != 0]
            daily_pnl = sum(float(d.get("profit", 0)) + float(d.get("swap", 0)) + float(d.get("commission", 0)) for d in today_deals)

            # Build a map of position profit by open time for live positions
            pos_profit_map = {}
            for p in live_positions:
                pos_time = p.get("time", "")
                pos_profit_map[pos_time] = p.get("profit", 0)

            # Walk through deals chronologically building cumulative equity
            running_equity = 0.0
            for deal in sorted(deals, key=lambda d: d.get("time", "")):
                deal_type = deal.get("type", "")
                deal_time = deal.get("time", "")
                deal_profit = float(deal.get("profit", 0))
                deal_swap = float(deal.get("swap", 0))
                deal_commission = float(deal.get("commission", 0))

                if deal_type == "DEAL_TYPE_BALANCE":
                    # Deposit/withdrawal
                    running_equity += deal_profit
                    try:
                        dt = datetime.fromisoformat(deal_time.replace("Z", "+00:00"))
                        label = dt.strftime("%b %d")
                    except Exception:
                        label = "Deposit"
                    equity_data.append({"time": label, "pnl": round(running_equity, 2)})

                elif deal_type in ("DEAL_TYPE_BUY", "DEAL_TYPE_SELL"):
                    # Closed deal has profit != 0, opening deal has profit == 0
                    if deal_profit != 0:
                        # This is a closing deal with realized PnL
                        running_equity += deal_profit + deal_swap + deal_commission
                        try:
                            dt = datetime.fromisoformat(deal_time.replace("Z", "+00:00"))
                            label = dt.strftime("%b %d %H:%M")
                        except Exception:
                            label = "Trade"
                        equity_data.append({"time": label, "pnl": round(running_equity, 2)})
                    else:
                        # Opening deal — find live unrealized profit for this position
                        live_profit = pos_profit_map.get(deal_time, 0)
                        running_equity += live_profit + deal_swap + deal_commission
                        try:
                            dt = datetime.fromisoformat(deal_time.replace("Z", "+00:00"))
                            label = dt.strftime("%b %d %H:%M")
                        except Exception:
                            label = "Open"
                        symbol = deal.get("symbol", "")
                        equity_data.append({"time": f"{label} {symbol}", "pnl": round(running_equity, 2)})

            # Add a "Now" point with current equity
            equity_data.append({"time": "Now", "pnl": round(cast(float, current_equity), 2)})

        except Exception as e:
            logger.error(f"Failed to build equity curve from deal history: {e}")
            equity_data = [{"time": "Today", "pnl": round(cast(float, current_equity), 2)}]

    # Fallback if no MetaApi or no deals
    if not equity_data:
        # Sort oldest first for equity curve
        chronological_trades = sorted(closed_trades, key=lambda x: x["created_at"] if x["created_at"] else datetime.min)
        
        historical_equity = cast(float, current_equity) - realized_float
        for t in chronological_trades:
            historical_equity += t["pnl"]
            equity_data.append({
                "time": t["created_at"].strftime("%b %d") if t["created_at"] else "Unknown",
                "pnl": round(historical_equity, 2)
            })
            
        if not equity_data:
            equity_data = [{"time": "Today", "pnl": round(cast(float, current_equity), 2)}]

    return {
        "account_balance": round(cast(float, current_balance), 2),
        "active_trades": active_trades_count,
        "win_rate": round(cast(float, win_rate), 2),
        "profit_factor": profit_factor,
        "total_pnl": total_pnl,
        "unrealized_pnl": round(unrealized_float, 2),
        "daily_pnl": round(daily_pnl, 2),
        "equity_curve": equity_data[-30:]
    }


@router.get("/debug/{trade_id}")
async def debug_trade_status(trade_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Lightweight debugging endpoint for trade/state consistency.
    """
    trade = db.query(Trade).filter(Trade.id == trade_id, Trade.user_id == user.id).first()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")

    state = db.query(TradeState).filter(
        TradeState.position_id == trade_id,
        TradeState.user_id == user.id
    ).order_by(TradeState.updated_at.desc()).first()

    position = db.query(Position).filter(Position.id == trade_id, Position.user_id == user.id).first()

    return {
        "trade_id": trade.id,
        "trade_status": trade.status,
        "trade_result": trade.result,
        "trade_retry_count": trade.retry_count or 0,
        "trade_last_synced_at": trade.last_synced_at.isoformat() if trade.last_synced_at else None,
        "state_status": state.status if state else None,
        "state_last_checked_at": state.last_checked_at.isoformat() if state and state.last_checked_at else None,
        "position_status": position.status if position else None,
        "position_exit_price": position.exit_price if position else None,
        "position_pnl": position.pnl if position else None,
    }
