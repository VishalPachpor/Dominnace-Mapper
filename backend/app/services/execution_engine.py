import ccxt
import os
import logging
import uuid

logger = logging.getLogger(__name__)

MT5_SYMBOLS = [
    # Forex pairs
    "USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD",
    # Metals & Energy
    "XAU", "XAG", "NATGAS", "XNG", "OIL",
    # Crypto CFDs (traded on MetaApi MT5 brokers like Fusion Markets)
    "BTC", "ETH", "LTC", "XRP", "SOL",
]

def is_forex_symbol(symbol: str):
    return any(p in symbol.upper() for p in MT5_SYMBOLS)

class ExecutionEngine:

    def __init__(self):
        # Crypto engine (Binance mock for now)
        self.crypto_exchange = ccxt.binance({
            'enableRateLimit': True,
        })
        if os.getenv("BINANCE_TESTNET", "True") == "True":
            self.crypto_exchange.set_sandbox_mode(True)

    async def open_trade(self, user, trade_dict):
        symbol = trade_dict["symbol"]
        side = trade_dict["side"]
        volume = 0.01 # Minimum valid lot size for MT5 CFD instruments
        sl = trade_dict.get("sl", 0)
        tp = trade_dict.get("tp", 0)

        logger.info(f"ExecutionEngine: Routing trade {side} {volume} {symbol} for User {user.id}")

        if is_forex_symbol(symbol):
            # EA Bridge Safety Check
            if not getattr(user, "ea_token", None):
                logger.warning(f"User {user.id} has no EA Token. MT5 Expert Advisor is not connected.")
                return None
            
            # Risk Control Example
            FOREX_MAX_VOLUME = 5.0
            if volume > FOREX_MAX_VOLUME:
                logger.warning(f"Volume {volume} exceeds safety limits. Capping at {FOREX_MAX_VOLUME}")
                volume = FOREX_MAX_VOLUME

            logger.info(f"Enqueuing {symbol} for MT5 EA Bridge execution")
            return {
                "orderId": str(uuid.uuid4()),
                "status": "pending_ea"
            }

        else:
            # Route to Crypto
            logger.info(f"Routing {symbol} to CryptoEngine (Binance)")
            try:
                if side.lower() == "buy":
                    logger.debug(f"Mocking Crypto: create_market_buy_order({symbol}, {volume})")
                else:
                    logger.debug(f"Mocking Crypto: create_market_sell_order({symbol}, {volume})")
                
                logger.info("Crypto trade opened successfully (Mocked).")
                return {"status": "success", "broker": "binance", "mock": True}
            except Exception as e:
                logger.error(f"Error executing crypto trade: {e}")
                return None
