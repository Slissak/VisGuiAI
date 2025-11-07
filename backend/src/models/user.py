"""User model for authentication and tier management."""

import enum

from sqlalchemy import Boolean, Column, DateTime, String
from sqlalchemy.sql import func

from .database import Base


class UserTier(str, enum.Enum):
    """User tier levels for quota management."""

    FREE = "free"
    BASIC = "basic"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class UserModel(Base):
    """User model for authentication and authorization."""

    __tablename__ = "users"

    user_id = Column(String(255), primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)

    # User tier for quota management
    tier = Column(String, nullable=False, default=UserTier.FREE.value)

    # User profile
    full_name = Column(String(255), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    is_verified = Column(Boolean, nullable=False, default=False)
    is_admin = Column(Boolean, nullable=False, default=False)

    # Timestamps
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    # Email verification
    verification_token = Column(String(255), nullable=True)
    verification_token_expires = Column(DateTime(timezone=True), nullable=True)

    # Password reset
    reset_token = Column(String(255), nullable=True)
    reset_token_expires = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    # Note: UserUsage relationship defined in usage.py to avoid circular imports

    def __repr__(self):
        return f"<User {self.user_id} ({self.email}) - {self.tier}>"
