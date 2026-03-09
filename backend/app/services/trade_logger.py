import logging
from app.database.db import SessionLocal
from app.models.trade import Trade

logger = logging.getLogger(__name__)

def log_trade(trade_data):
    db = SessionLocal()
    try:
        trade = Trade(
            id=trade_data.get("id"),
            user_id=trade_data.get("user_id"),
            symbol=trade_data.get("symbol"),
            side=trade_data.get("side"),
            entry=trade_data.get("entry"),
            exit=trade_data.get("exit"),
            pnl=trade_data.get("pnl"),
            result=trade_data.get("result")
        )
        db.add(trade)
        db.commit()
        logger.info(f"Successfully logged completed trade {trade.id} with PnL: {trade.pnl}")
    except Exception as e:
        logger.error(f"Error logging trade: {e}")
        db.rollback()
    finally:
        db.close()
