import asyncio
import logging
import time
import os
import sentry_sdk
from app.services.trade_monitor import TradeMonitorService
from app.routes.admin.admin_system import is_trading_enabled

# Initialize Sentry
sentry_dsn = os.getenv("SENTRY_DSN")
if sentry_dsn:
    sentry_sdk.init(dsn=sentry_dsn, traces_sample_rate=1.0)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

async def start_monitor():
    monitor = TradeMonitorService()
    logger.info("Trade Monitor worker started. Checking positions for BE/Reversal every 60s...")
    
    while True:
        try:
            if not is_trading_enabled():
                logger.warning("Kill switch active — Monitor skipping cycle.")
                await asyncio.sleep(10)
                continue
            
            start_time = time.time()
            await monitor.monitor_all_trades()
            elapsed = time.time() - start_time
            
            logger.info(f"Monitor cycle completed in {elapsed:.2f}s")
            
            # Wait for the remainder of the 10s cycle
            sleep_time = max(2, 10 - elapsed)
            await asyncio.sleep(sleep_time)
            
        except Exception as e:
            sentry_sdk.capture_exception(e)
            logger.error(f"Monitor Worker Error: {e}")
            await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(start_monitor())
