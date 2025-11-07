"""User usage tracking model for token limits and cost tracking."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.models.database import Base


class UserUsage(Base):
    """Track user's daily and monthly usage/costs for quota enforcement."""

    __tablename__ = "user_usage"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        String(255),
        ForeignKey("users.user_id"),
        nullable=False,
        index=True,
        unique=True,
    )

    # Daily tracking
    daily_cost = Column(Float, default=0.0, nullable=False)
    daily_requests = Column(Integer, default=0, nullable=False)
    daily_reset_date = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Monthly tracking
    monthly_cost = Column(Float, default=0.0, nullable=False)
    monthly_requests = Column(Integer, default=0, nullable=False)
    monthly_reset_date = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Limits exceeded flags
    daily_budget_exceeded = Column(Boolean, default=False, nullable=False)
    monthly_budget_exceeded = Column(Boolean, default=False, nullable=False)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    user = relationship("UserModel", backref="usage", uselist=False)
