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
        # Crypto engine (Binance)
        self.crypto_exchange = ccxt.binance({
            'enableRateLimit': True,
        })
        if os.getenv("BINANCE_TESTNET", "True") == "True":
            self.crypto_exchange.set_sandbox_mode(True)

    async def open_trade(self, user, trade_dict):
        symbol = trade_dict["symbol"]
        side = trade_dict["side"]
        volume = float(trade_dict.get("volume", 0.01))
        sl = float(trade_dict.get("sl", 0))
        tp = float(trade_dict.get("tp", 0))

        logger.info(f"ExecutionEngine: Routing trade {side} {volume} {symbol} for User {user.id}")

        if is_forex_symbol(symbol):
            # ── Guard 1: MetaApi terminal must be connected ───────────────────
            mt_status = getattr(user, "mt_status", None)
            meta_account_id = getattr(user, "meta_account_id", None)

            if not meta_account_id or mt_status != "connected":
                logger.warning(
                    f"User {user.id} MT5 terminal not ready "
                    f"(status={mt_status}, account={meta_account_id}). Skipping trade."
                )
                return None

            # ── Guard 2: Duplicate position check ─────────────────────────────
            from app.services.metaapi_service import has_open_position, execute_trade
            if await has_open_position(meta_account_id, symbol):
                logger.info(f"Duplicate guard: skipping {symbol} — position already open.")
                return {"status": "skipped", "reason": "duplicate_position"}

            # ── Execute via MetaApi ───────────────────────────────────────────
            result = await execute_trade(
                account_id=meta_account_id,
                symbol=symbol,
                side=side,
                volume=volume,
                sl=sl,
                tp=tp
            )
            return {"status": "success", "broker": "metaapi", "result": result}

        else:
            # Route to Crypto (Binance)
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

