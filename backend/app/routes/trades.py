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
def get_trades(user = Depends(get_current_user), db: Session = Depends(get_db)):
    trades = db.query(Trade).filter(Trade.user_id == user.id).order_by(Trade.created_at.desc()).all()
    return trades

@router.get("/dashboard")
def get_dashboard_stats(user = Depends(get_current_user), db: Session = Depends(get_db)):

    # 1. Fetch Real Balance AND Live Positions
    current_equity = 10000.0
    active_trades = 0
    unrealized_pnl = 0.0
    balance_fetched = False

    # A. Check EA Bridge MT5 Balance
    if getattr(user, "mt5_equity", 0.0) > 0:
        current_equity = user.mt5_equity
        unrealized_pnl = round(user.mt5_equity - getattr(user, "mt5_balance", 0.0), 2)
        # Count open positions picked up by EA
        active_trades = db.query(Position).filter(
            Position.user_id == user.id, 
            Position.status.in_(["pending_ea", "picked_up", "executed"])
        ).count()
        balance_fetched = True
        logger.info(f"EA Bridge equity fetched: {current_equity} for user {user.id}")

    # B. Legacy MetaApi fallback
    elif getattr(user, "meta_account_id", None):
        try:
            import httpx
            from app.config import META_API_TOKEN

            base = "https://mt-client-api-v1.new-york.agiliumtrade.ai"
            acct = user.meta_account_id
            headers = {"auth-token": META_API_TOKEN}

            with httpx.Client(verify=False, timeout=10.0) as client:
                info_resp = client.get(f"{base}/users/current/accounts/{acct}/account-information", headers=headers)
                if info_resp.status_code == 200:
                    info_data = info_resp.json()
                    current_equity = float(info_data.get("equity", info_data.get("balance", current_equity)))
                    balance_fetched = True

                pos_resp = client.get(f"{base}/users/current/accounts/{acct}/positions", headers=headers)
                if pos_resp.status_code == 200:
                    positions = pos_resp.json()
                    active_trades = len(positions)
                    unrealized_pnl = sum(float(p.get("profit", 0)) for p in positions)
        except Exception as e:
            logger.error(f"Failed to fetch MetaApi data for user {user.id}: {str(e)}")

    # Fallback to Binance if MetaApi not configured
    if not balance_fetched and user.exchange_api_key and user.exchange_secret_key:
        try:
            exchange = ccxt.binance({
                'apiKey': user.exchange_api_key,
                'secret': user.exchange_secret_key,
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
    # Explicitly hint Pyre that `realized_pnl` is a float
    realized_float = cast(float, sum([float(t.pnl) for t in trades if t.pnl is not None]))
    unrealized_float = cast(float, unrealized_pnl)
    total_pnl = round(realized_float + unrealized_float, 2)

    wins = len([t for t in trades if t.result == "WIN"])
    total_closed = len(trades)
    win_rate = (wins / total_closed * 100) if total_closed > 0 else 0

    # 3. Equity curve from closed trade history
    equity_data = []
    historical_equity = cast(float, current_equity) - realized_float
    for t in sorted(trades, key=lambda x: x.created_at):
        if t.pnl is not None:
            historical_equity += float(t.pnl)
        equity_data.append({
            "time": t.created_at.strftime("%b %d"),
            "pnl": round(historical_equity, 2)
        })

    if not equity_data:
        equity_data = [{"time": "Today", "pnl": round(current_equity, 2)}]

    return {
        "account_balance": round(cast(float, current_equity), 2),
        "active_trades": active_trades,
        "win_rate": round(cast(float, win_rate), 2),
        "total_pnl": total_pnl,
        "unrealized_pnl": round(unrealized_float, 2),
        "equity_curve": [e for e in equity_data][-20:]
    }

