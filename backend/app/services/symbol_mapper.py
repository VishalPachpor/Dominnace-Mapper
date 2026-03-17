"""
Dynamic broker symbol resolver.

Priority order:
  1. Exact match (BTCUSD in account_symbols)
  2. Static SYMBOL_MAP lookup (BTCUSDT → [BTCUSD, BTCUSDm, ...])
  3. Dynamic strip: BTCUSDT → BTCUSD, scan for any account symbol containing base
  4. Raise ExecutionValidationError("SYMBOL_NOT_SUPPORTED")

This makes the system broker-agnostic without needing a hardcoded map for every broker.
"""

import logging
from app.services.exceptions import ExecutionValidationError

logger = logging.getLogger(__name__)

# Static fallback map for common signal symbols → broker variants.
# Add entries when a specific broker requires a non-standard suffix.
SYMBOL_MAP: dict[str, list[str]] = {
    "BTCUSDT": ["BTCUSD", "BTCUSDm", "BTCUSD.pro", "BTCUSD_m", "BTC/USD"],
    "ETHUSDT": ["ETHUSD", "ETHUSDm", "ETHUSD.pro", "ETHUSD_m", "ETH/USD"],
    "BNBUSDT": ["BNBUSD", "BNBUSDm"],
    "SOLUSDT": ["SOLUSD", "SOLUSDm"],
    "XAUUSD":  ["XAUUSD", "GOLD", "XAUUSDm", "XAUUSD.pro", "XAUUSDc"],
    "XAGUSD":  ["XAGUSD", "SILVER", "XAGUSDm"],
    "EURUSD":  ["EURUSD", "EURUSDm", "EURUSD.pro"],
    "GBPUSD":  ["GBPUSD", "GBPUSDm"],
    "USDJPY":  ["USDJPY", "USDJPYm"],
}


def resolve_symbol(signal_symbol: str, account_symbols: list[str]) -> str:
    """
    Maps the raw signal symbol to one that actually exists on the broker account.

    Args:
        signal_symbol:  Symbol from TradingView signal (e.g. "BTCUSDT")
        account_symbols: All symbols available on the connected MT5 account

    Returns:
        Matched broker symbol string (e.g. "BTCUSDm")

    Raises:
        ExecutionValidationError("SYMBOL_NOT_SUPPORTED") if no match is found
    """
    # 1. Exact match — fastest path (most brokers use the same symbol)
    if signal_symbol in account_symbols:
        logger.debug(f"[SymbolMapper] Exact match: {signal_symbol}")
        return signal_symbol

    # 2. Static map — check all known aliases
    candidates = SYMBOL_MAP.get(signal_symbol, [])
    for candidate in candidates:
        if candidate in account_symbols:
            logger.info(f"[SymbolMapper] Static map: {signal_symbol} → {candidate}")
            return candidate

    # 3. Dynamic strip: BTCUSDT → BTCUSD, then fuzzy match any broker suffix
    #    e.g. "BTCUSDm", "BTCUSD.pro", "BTCUSD_m"
    base = signal_symbol.replace("USDT", "USD").replace("BUSD", "USD")
    for sym in account_symbols:
        if sym.startswith(base):
            logger.info(f"[SymbolMapper] Dynamic strip match: {signal_symbol} → {sym}")
            return sym

    # 4. Partial contains match (last resort)
    for sym in account_symbols:
        if base in sym:
            logger.info(f"[SymbolMapper] Partial contains match: {signal_symbol} → {sym}")
            return sym

    # Nothing worked
    logger.warning(
        f"[SymbolMapper] SYMBOL_NOT_SUPPORTED: '{signal_symbol}'. "
        f"Tried candidates: {candidates}. "
        f"Account symbols sample: {account_symbols[:10]}"
    )
    raise ExecutionValidationError(
        "SYMBOL_NOT_SUPPORTED",
        f"Symbol '{signal_symbol}' could not be mapped to any broker symbol. "
        f"Add this symbol to SYMBOL_MAP or check your broker account."
    )
