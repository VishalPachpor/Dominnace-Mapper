from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.utils.subscription_check import check_subscription_active
from app.models.user import User
from app.models.trade import Trade
from app.models.position import Position
from app.database.db import get_db
from app.utils.security import get_current_user
import ccxt
from typing import cast
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("")
async def get_trades(user = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Returns closed trades from DB + live open positions from MetaApi.
    Open positions are marked with result='OPEN' so the frontend can distinguish them.
    """
    # 1. Closed trades from DB
    closed_trades = db.query(Trade).filter(Trade.user_id == user.id).order_by(Trade.created_at.desc()).all()
    result_list = []
    for t in closed_trades:
        result_list.append({
            "id": t.id,
            "symbol": t.symbol,
            "side": t.side,
            "entry_price": t.entry,
            "exit_price": t.exit,
            "pnl": t.pnl,
            "result": t.result or "CLOSED",
            "volume": 0.01,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "status": "closed",
        })

    # 2. Live open positions from MetaApi
    meta_account_id = getattr(user, "meta_account_id", None)
    if meta_account_id:
        try:
            from app.services.metaapi_service import get_open_positions
            positions = await get_open_positions(meta_account_id)
            for p in positions:
                side_raw = p.get("type", "")
                side = "buy" if "BUY" in side_raw.upper() else "sell"
                result_list.append({
                    "id": p.get("id", ""),
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
                })
        except Exception as e:
            logger.error(f"Failed to fetch live positions for trades list: {e}")

    return result_list

@router.get("/dashboard")
async def get_dashboard_stats(user = Depends(get_current_user), db: Session = Depends(get_db)):

    # 1. Fetch Real Balance AND Live Positions
    current_equity = 10000.0
    active_trades = 0
    unrealized_pnl = 0.0
    balance_fetched = False

    # A. Check EA Bridge MT5 Balance
    if getattr(user, "mt5_equity", 0.0) > 0:
        current_equity = user.mt5_equity
        unrealized_pnl = round(user.mt5_equity - getattr(user, "mt5_balance", 0.0), 2)
        active_trades = db.query(Position).filter(
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
                current_equity = float(info.get("equity", info.get("balance", current_equity)))
                balance_fetched = True

            positions = await get_open_positions(acct)
            active_trades = len(positions)
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
                current_equity = float(balance['total']['USDT'])
                balance_fetched = True
        except Exception as e:
            logger.error(f"Failed to fetch CCXT Binance balance for user {user.id}: {str(e)}")

    # 2. Total PNL & Win Rate from closed trades (historical)
    trades = db.query(Trade).filter(Trade.user_id == user.id).all()
    realized_float = cast(float, sum([float(t.pnl) for t in trades if t.pnl is not None]))
    unrealized_float = cast(float, unrealized_pnl)
    total_pnl = round(realized_float + unrealized_float, 2)

    wins = len([t for t in trades if t.result == "WIN"])
    total_closed = len(trades)
    win_rate = (wins / total_closed * 100) if total_closed > 0 else 0

    # 3. Equity curve — built from MetaApi deal history + live positions
    equity_data = []
    meta_account_id = getattr(user, "meta_account_id", None)

    if meta_account_id:
        try:
            from app.services.metaapi_service import get_deal_history, get_open_positions as get_pos
            from datetime import datetime

            deals = await get_deal_history(meta_account_id)
            live_positions = await get_pos(meta_account_id)

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
        # Use DB trades if available
        historical_equity = cast(float, current_equity) - realized_float
        for t in sorted(trades, key=lambda x: x.created_at):
            if t.pnl is not None:
                historical_equity += float(t.pnl)
            equity_data.append({
                "time": t.created_at.strftime("%b %d"),
                "pnl": round(historical_equity, 2)
            })
        if not equity_data:
            equity_data = [{"time": "Today", "pnl": round(cast(float, current_equity), 2)}]

    return {
        "account_balance": round(cast(float, current_equity), 2),
        "active_trades": active_trades,
        "win_rate": round(cast(float, win_rate), 2),
        "total_pnl": total_pnl,
        "unrealized_pnl": round(unrealized_float, 2),
        "equity_curve": equity_data[-30:]
    }

