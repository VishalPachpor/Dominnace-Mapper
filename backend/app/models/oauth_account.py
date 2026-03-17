from sqlalchemy import Column, String, DateTime, ForeignKey, Enum, UniqueConstraint
from app.database.db import Base
from sqlalchemy.orm import relationship
from uuid import uuid4
from datetime import datetime
import enum

class AuthProvider(str, enum.Enum):
    GOOGLE = "google"
    APPLE = "apple"
    GITHUB = "github"
    DISCORD = "discord"

class OAuthAccount(Base):
    __tablename__ = "oauth_accounts"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    provider = Column(Enum(AuthProvider), nullable=False)
    provider_sub = Column(String(255), nullable=False)
    provider_email = Column(String(255), nullable=False, index=True)
    
    # Metadata for UI enhancement
    provider_name = Column(String(200), nullable=True)
    provider_avatar = Column(String(500), nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    last_used_at = Column(DateTime, default=lambda: datetime.utcnow(), onupdate=lambda: datetime.utcnow())

    user = relationship("User", back_populates="oauth_accounts")

    __table_args__ = (
        UniqueConstraint("provider", "provider_sub", name="uix_provider_sub"),
    )
