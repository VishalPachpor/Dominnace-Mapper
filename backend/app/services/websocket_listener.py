import websocket
import json
import logging
from app.services.position_monitor import check_break_even

logger = logging.getLogger(__name__)
# placeholder for in-memory or db fetched positions that need tight monitoring
active_positions = {} 

def process_price_update(symbol, price):
    # Retrieve active positions for this symbol
    positions = active_positions.get(symbol, [])
    
    for pos in positions:
        # Check BE
        check_break_even(pos, price)
        # We would also check SL/TP hits here to invoke Reversal/Close logic
        # if price <= pos["sl"] -> handle reverse or loss
        # if price >= pos["tp"] -> handle take profit

def on_message(ws, message):
    try:
        data = json.loads(message)
        # lowercase symbol from stream e.g 'btcusdt@trade'
        symbol = data["s"].upper()
        price = float(data["p"])
        
        process_price_update(symbol, price)
    except Exception as e:
        logger.error(f"Error processing websocket message: {e}")

def on_error(ws, error):
    logger.error(f"Websocket error: {error}")

def on_close(ws, close_status_code, close_msg):
    logger.warning("Binance WebSocket closed")

def on_open(ws):
    logger.info("Binance WebSocket stream completely opened")
    # Subscribing to BTCUSDT trade stream as an example
    # Multiple streams can be listened to: e.g. btcusdt@trade, ethusdt@trade
    params = {
        "method": "SUBSCRIBE",
        "params": [
            "btcusdt@trade"
        ],
        "id": 1
    }
    ws.send(json.dumps(params))

def start_websocket_stream():
    url = "wss://stream.binance.com:9443/ws"
    
    ws = websocket.WebSocketApp(url,
                                on_open=on_open,
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)
    
    logger.info("Starting WebSocket listener...")
    ws.run_forever()

if __name__ == "__main__":
    import threading
    # Basic setup to initialize logger locally if run directly
    logging.basicConfig(level=logging.INFO)
    start_websocket_stream()
