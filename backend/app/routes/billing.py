from fastapi import APIRouter, Header, Request, HTTPException, Depends
from sqlalchemy.orm import Session
from app.database.db import get_db
from app.config import NOWPAYMENTS_API_KEY, NOWPAYMENTS_IPN_SECRET, FRONTEND_URL
from datetime import datetime, timedelta, timezone
from app.models.subscription import Subscription
from app.utils.security import get_current_user
import httpx
import hmac
import hashlib
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

PLAN_PRICES = {
    "starter": 49.00,
    "pro": 99.00,
    "elite": 249.00
}

@router.post("/create-payment")
async def create_crypto_payment(
    plan: str, 
    pay_currency: str = "usdt", 
    user = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    try:
        plan_lower = plan.lower()
        price = PLAN_PRICES.get(plan_lower)
        if not price:
            raise HTTPException(status_code=400, detail="Invalid plan selected")

        if not NOWPAYMENTS_API_KEY:
            raise HTTPException(status_code=500, detail="NOWPayments API key not configured")

        url = "https://api.nowpayments.io/v1/payment"
        payload = {
            "price_amount": price,
            "price_currency": "usd",
            "pay_currency": pay_currency,
            "order_id": str(user.id),
            "order_description": f"{plan.capitalize()} Plan Subscription"
        }
        headers = {
            "x-api-key": NOWPAYMENTS_API_KEY,
            "Content-Type": "application/json"
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        # Update or create pending subscription
        sub = db.query(Subscription).filter(Subscription.user_id == user.id).first()
        if not sub:
            sub = Subscription(user_id=user.id)
            db.add(sub)
        
        sub.payment_provider = "nowpayments"
        sub.crypto_payment_id = str(data.get("payment_id"))
        sub.payment_currency = pay_currency
        sub.plan = plan_lower
        sub.status = "pending"
        db.commit()

        # Returns payment_id, pay_address, pay_amount, etc.
        return data

    except httpx.HTTPError as e:
        logger.error(f"NOWPayments API Error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to communicate with crypto payment provider")
    except Exception as e:
        logger.error(f"Generate Crypto Invoice Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/webhook")
async def nowpayments_webhook(request: Request, x_nowpayments_sig: str = Header(None), db: Session = Depends(get_db)):
    payload = await request.body()
    
    # 1. Verify HMAC Signature
    if not NOWPAYMENTS_IPN_SECRET or not x_nowpayments_sig:
        raise HTTPException(status_code=400, detail="Missing signature or IPN secret")

    hmac_obj = hmac.new(
        NOWPAYMENTS_IPN_SECRET.encode('utf-8'),
        payload,
        hashlib.sha512
    )
    expected_sig = hmac_obj.hexdigest()

    if not hmac.compare_digest(expected_sig, x_nowpayments_sig):
        logger.warning("Invalid NOWPayments webhook signature")
        raise HTTPException(status_code=400, detail="Invalid signature")

    # 2. Process Payload
    try:
        data = json.loads(payload.decode('utf-8'))
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    payment_id = str(data.get("payment_id"))
    payment_status = data.get("payment_status")
    
    # finished means payment is fully confirmed on blockchain
    if payment_status == "finished":
        sub = db.query(Subscription).filter(Subscription.crypto_payment_id == payment_id).first()
        if sub:
            sub.status = "active"
            sub.crypto_tx_hash = data.get("payin_hash") or data.get("tx_hash")
            sub.current_period_end = datetime.now(timezone.utc) + timedelta(days=30)
            db.commit()
            logger.info(f"Activated subscription for user {sub.user_id} via crypto payment {payment_id}")
        else:
            logger.warning(f"Received finished webhook for unknown payment_id: {payment_id}")

    return {"status": "success"}
