import ccxt

class ExchangeClient:

    def __init__(self, api_key, secret):

        self.exchange = ccxt.binance({
            "apiKey": api_key,
            "secret": secret
        })

    def get_price(self, symbol):

        ticker = self.exchange.fetch_ticker(symbol)

        return ticker["last"]
