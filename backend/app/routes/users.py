from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.database.db import get_db
from app.utils.security import get_current_user

router = APIRouter()


class AddApiKeyRequest(BaseModel):
    api_key: str
    secret_key: str

@router.post("/add-api-key")
def save_api_keys(data: AddApiKeyRequest, user=Depends(get_current_user), db: Session = Depends(get_db)):
    user.exchange_api_key = data.api_key
    user.exchange_secret_key = data.secret_key
    db.commit()
    return {"message": "API keys saved successfully"}

@router.post("/ea-token")
def generate_ea_token(user=Depends(get_current_user), db: Session = Depends(get_db)):
    import uuid
    user.ea_token = str(uuid.uuid4())
    db.commit()
    return {"message": "EA Token generated", "ea_token": user.ea_token}

@router.get("/ea-token")
def get_ea_token(user=Depends(get_current_user)):
    return {
        "ea_token": user.ea_token,
        "ea_last_seen": user.ea_last_seen
    }

@router.get("/")
def get_users():
    return {"message": "Users endpoint"}
