from pydantic import BaseModel

class PositionBase(BaseModel):
    symbol: str
    side: str
    entry: float
    sl: float
    tp: float
    be_trigger: float
    is_reversal: bool = False
    be_moved: bool = False
    status: str

class PositionResponse(PositionBase):
    id: str
    user_id: str | None = None

    class Config:
        from_attributes = True
