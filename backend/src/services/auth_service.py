"""Authentication service for user management and authentication."""

import uuid
from datetime import datetime

from fastapi import HTTPException, status
from passlib.context import CryptContext
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.user import UserModel

# Password hashing context using bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """
    Hash a plain text password using bcrypt.

    Args:
        password: The plain text password to hash

    Returns:
        The hashed password string
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain text password against a hashed password.

    Args:
        plain_password: The plain text password to verify
        hashed_password: The hashed password to verify against

    Returns:
        True if the password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


async def get_user_by_email(db: AsyncSession, email: str) -> UserModel | None:
    """
    Look up a user by email address (case-insensitive).

    Args:
        db: The database session
        email: The email address to search for

    Returns:
        The UserModel if found, None otherwise
    """
    stmt = select(UserModel).where(func.lower(UserModel.email) == func.lower(email))
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: str) -> UserModel | None:
    """
    Look up a user by their user ID.

    Args:
        db: The database session
        user_id: The user ID to search for

    Returns:
        The UserModel if found, None otherwise
    """
    stmt = select(UserModel).where(UserModel.user_id == user_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def create_user(
    db: AsyncSession,
    email: str,
    password: str,
    full_name: str | None = None,
    tier: str = "free",
) -> UserModel:
    """
    Create a new user account.

    Args:
        db: The database session
        email: The user's email address
        password: The user's plain text password (will be hashed)
        full_name: Optional full name of the user
        tier: The user tier (default: "free")

    Returns:
        The created UserModel

    Raises:
        HTTPException: If the email already exists (status 400)
    """
    # Check if email already exists (case-insensitive)
    existing_user = await get_user_by_email(db, email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )

    # Generate unique user ID
    user_id = str(uuid.uuid4())

    # Hash the password
    hashed_password = hash_password(password)

    # Create new user
    new_user = UserModel(
        user_id=user_id,
        email=email,
        hashed_password=hashed_password,
        full_name=full_name,
        tier=tier,
        is_active=True,
        is_verified=False,
    )

    # Add to database
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return new_user


async def authenticate_user(
    db: AsyncSession, email: str, password: str
) -> UserModel | None:
    """
    Authenticate a user by email and password.

    Args:
        db: The database session
        email: The user's email address
        password: The user's plain text password

    Returns:
        The UserModel if authentication succeeds, None otherwise
    """
    # Look up user by email (case-insensitive)
    user = await get_user_by_email(db, email)
    if not user:
        return None

    # Verify password
    if not verify_password(password, user.hashed_password):
        return None

    # Update last login timestamp
    user.last_login_at = datetime.utcnow()
    await db.commit()
    await db.refresh(user)

    return user
