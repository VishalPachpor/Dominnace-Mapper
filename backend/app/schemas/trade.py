from pydantic import BaseModel

class TradeBase(BaseModel):
    symbol: str
    side: str
    entry: float
    exit: float | None = None
    pnl: float | None = None
    result: str | None = None

class TradeResponse(TradeBase):
    id: str
    user_id: str | None = None
    
    class Config:
        from_attributes = True
