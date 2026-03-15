import json
import asyncio
from app.utils.redis_client import redis_client
from app.services.trade_manager import TradeManager
from app.routes.admin import is_trading_enabled
from app.utils.metrics import (
    signals_processed_total,
    worker_processing_latency_seconds,
    redis_queue_length,
    redis_queue_wait_seconds,
)
import time
import logging
import os
import sentry_sdk

# Initialize Sentry for error tracking
sentry_dsn = os.getenv("SENTRY_DSN")
if sentry_dsn:
    sentry_sdk.init(
        dsn=sentry_dsn,
        traces_sample_rate=1.0,
        profiles_sample_rate=1.0,
    )

from prometheus_client import start_http_server

# Initialize logging so all trade processing events appear in Docker logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)

manager = TradeManager()

def start_worker():
    start_http_server(8001)  # Export metrics on port 8001 for Prometheus to scrape
    logger.info("Signal worker started. Listening for signals on port 8001 (metrics)...")
    while True:
        try:
            # Measure queue length periodically per cycle
            q_len = redis_client.llen("signal_queue")
            redis_queue_length.set(q_len)

            signal = redis_client.rpop("signal_queue")

            if signal:
                if not is_trading_enabled():
                    logger.warning("Kill switch active — signal discarded.")
                    time.sleep(1)
                    continue
                
                data = json.loads(signal)
                bot_slug = data.get("bot", "UNKNOWN")
                logger.info(f"Processing signal: {data}")

                # Optional wait time (requires webhook injection of timestamp, assuming not present right now)
                
                # Signal is actively being processed now
                signals_processed_total.labels(bot=bot_slug).inc()
                
                with worker_processing_latency_seconds.labels(bot=bot_slug).time():
                    asyncio.run(manager.process_signal(data))
            else:
                # Add a small sleep to prevent CPU spinning when queue is empty
                time.sleep(0.1)
        except Exception as e:
            sentry_sdk.capture_exception(e)
            logger.error(f"Worker Error: {e}")
            time.sleep(1)

if __name__ == "__main__":
    start_worker()
