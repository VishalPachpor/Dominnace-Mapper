import logging
from datetime import datetime, date
from sqlalchemy.orm import Session
from app.models.strategy_stats import StrategyStats
from app.models.platform_metrics import PlatformMetrics
from app.utils.redis_client import redis_client

logger = logging.getLogger(__name__)

class AnalyticsService:
    @staticmethod
    def update_trade_metrics(db: Session, bot_slug: str, pnl: float):
        """Updates both strategy-specific and platform-wide trade metrics."""
        try:
            # 1. Update Strategy Stats
            stats = db.query(StrategyStats).filter(StrategyStats.bot_slug == bot_slug).first()
            if not stats:
                stats = StrategyStats(bot_slug=bot_slug)
                db.add(stats)
            
            stats.total_trades += 1
            stats.total_pnl += pnl
            if pnl > 0:
                stats.wins += 1
            elif pnl < 0:
                stats.losses += 1
            stats.last_updated = datetime.utcnow()

            # 2. Update Platform Metrics (Daily Snapshot)
            today = date.today()
            metrics = db.query(PlatformMetrics).filter(PlatformMetrics.date == today).first()
            if not metrics:
                metrics = PlatformMetrics(date=today)
                db.add(metrics)
            
            metrics.trades += 1
            
            # 3. Update Redis Counters (Today's observability)
            redis_client.incr("trades_today")
            
            db.commit()
        except Exception as e:
            logger.error(f"Failed to update analytics: {e}")
            db.rollback()

    @staticmethod
    def record_signal(db: Session):
        """Increments signal counters."""
        today = date.today()
        try:
            metrics = db.query(PlatformMetrics).filter(PlatformMetrics.date == today).first()
            if not metrics:
                metrics = PlatformMetrics(date=today)
                db.add(metrics)
            metrics.signals += 1
            db.commit()
            
            redis_client.incr("signals_today")
        except Exception as e:
            logger.error(f"Failed to record signal analytics: {e}")
            db.rollback()

    @staticmethod
    def record_new_user(db: Session):
        """Increments new user counter."""
        today = date.today()
        try:
            metrics = db.query(PlatformMetrics).filter(PlatformMetrics.date == today).first()
            if not metrics:
                metrics = PlatformMetrics(date=today)
                db.add(metrics)
            metrics.new_users += 1
            db.commit()
        except Exception as e:
            logger.error(f"Failed to record new user analytics: {e}")
            db.rollback()
