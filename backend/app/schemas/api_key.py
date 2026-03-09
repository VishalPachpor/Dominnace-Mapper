from pydantic import BaseModel

class APIKeyBase(BaseModel):
    exchange: str
    public_key: str

class APIKeyCreate(APIKeyBase):
    secret_key: str

class APIKeyResponse(APIKeyBase):
    id: str
    user_id: str | None = None

    class Config:
        from_attributes = True
