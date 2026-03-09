import json
import asyncio
from app.utils.redis_client import redis_client
from app.services.trade_manager import TradeManager
from app.routes.admin import is_trading_enabled
import time
import logging

# Initialize logging so all trade processing events appear in Docker logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)

manager = TradeManager()

def start_worker():
    logger.info("Signal worker started. Listening for signals...")
    while True:
        try:
            signal = redis_client.rpop("signal_queue")

            if signal:
                if not is_trading_enabled():
                    logger.warning("Kill switch active — signal discarded.")
                    time.sleep(1)
                    continue
                data = json.loads(signal)
                logger.info(f"Processing signal: {data}")
                asyncio.run(manager.process_signal(data))
            else:
                # Add a small sleep to prevent CPU spinning when queue is empty
                time.sleep(0.1)
        except Exception as e:
            logger.error(f"Worker Error: {e}")
            time.sleep(1)

if __name__ == "__main__":
    start_worker()
