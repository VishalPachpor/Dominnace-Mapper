import json
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.trade import Trade
from app.models.bot import Bot
from app.utils.redis_client import redis_client

def get_bot_leaderboard(db: Session):
    """
    Computes public performance metrics for all active bots to power 
    the SaaS marketing leaderboard.
    """
    # ── Critical Protection: Analytics Caching ──
    cached_board = redis_client.get("bot_leaderboard")
    if cached_board:
        return json.loads(cached_board)

    bots = db.query(Bot).filter(Bot.is_active == True).all()
    
    leaderboard = []
    for bot in bots:
        # Query aggregate statistics for the bot independent of which user took the trade
        # In a real massively scaled app, you would materialize this into a `bot_metrics_daily` table
        trades_query = db.query(Trade).filter(Trade.bot_id == bot.id)
        
        total_trades = trades_query.count()
        
        # We still return zero-trade bots so the frontend has something to display
        win_rate = 0.0
        total_pnl = 0.0
        
        if total_trades > 0:
            winning_trades = trades_query.filter(Trade.result == "WIN").count()
            win_rate = (winning_trades / total_trades) * 100
            total_pnl = db.query(func.sum(Trade.pnl)).filter(Trade.bot_id == bot.id).scalar() or 0.0
            
            # Additional metrics could go here:
            # - Max drawdown
            # - Average RR
            # - 30D rolling profit
        
        leaderboard.append({
            "bot_id": bot.id,
            "name": bot.name,
            "slug": bot.slug,
            "symbol": str(bot.symbol) if bot.symbol else "MULTI",
            "win_rate": round(win_rate, 2),
            "total_pnl": round(total_pnl, 2),
            "total_trades": total_trades
        })
        
    # Sort primarily by most profitable
    leaderboard.sort(key=lambda x: x["total_pnl"], reverse=True)
    
    # Cache for 5 minutes (300 seconds)
    redis_client.setex("bot_leaderboard", 300, json.dumps(leaderboard))
    
    return leaderboard
