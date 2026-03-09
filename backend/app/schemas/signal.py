from pydantic import BaseModel

class WebhookSignal(BaseModel):
    secret: str
    symbol: str
    action: str
    price: str
    dom_high: str | None = None
    dom_low: str | None = None
