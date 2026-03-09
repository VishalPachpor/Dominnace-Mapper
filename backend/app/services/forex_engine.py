import httpx
import logging
from app.config import META_API_TOKEN

logger = logging.getLogger(__name__)

class ForexEngine:

    # MetaApi REST endpoint baseURL
    BASE_URL = "https://mt-client-api-v1.new-york.agiliumtrade.ai"

    async def open_trade(self, account_id, symbol, side, volume, sl, tp):
        url = f"{self.BASE_URL}/users/current/accounts/{account_id}/trade"

        payload = {
            "symbol": symbol,
            "actionType": "ORDER_TYPE_BUY" if side.upper() == "BUY" else "ORDER_TYPE_SELL",
            "volume": volume,
        }

        # Only add SL/TP if they are valid non-zero values
        if sl and sl != 0:
            payload["stopLoss"] = sl
        if tp and tp != 0:
            payload["takeProfit"] = tp

        headers = {
            "auth-token": META_API_TOKEN
        }

        if not META_API_TOKEN:
            logger.error("META_API_TOKEN is not configured.")
            raise Exception("META_API_TOKEN is not configured.")

        logger.info(f"ForexEngine: Sending trade to MT5 for {symbol} ({side})")
        
        async with httpx.AsyncClient(verify=False) as client:
            resp = await client.post(url, json=payload, headers=headers)

        data = resp.json()
        
        if resp.status_code != 200 or data.get("stringCode") != "TRADE_RETCODE_DONE":
            error_msg = f"MetaApi Trade Error: {data.get('message', resp.text)} ({data.get('stringCode', 'Unknown')})"
            logger.error(error_msg)
            raise Exception(error_msg)

        logger.info(f"ForexEngine: Trade placed successfully on MT5.")
        return data
