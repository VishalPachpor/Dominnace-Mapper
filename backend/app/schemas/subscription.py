from pydantic import BaseModel
from datetime import datetime

class SubscriptionBase(BaseModel):
    user_id: str
    stripe_customer_id: str
    stripe_subscription_id: str
    plan: str
    status: str
    current_period_end: datetime

class SubscriptionResponse(SubscriptionBase):
    id: str

    class Config:
        from_attributes = True
