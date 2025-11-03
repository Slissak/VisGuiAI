"""Authentication middleware for JWT token validation."""

import jwt
from jwt.exceptions import PyJWTError
from typing import Optional, Callable
from datetime import datetime, timedelta

from fastapi import HTTPException, status, Depends, Request, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from ..core.config import get_settings
from ..core.database import get_db
from ..models.user import UserModel
from ..utils.logging import get_logger

settings = get_settings()
security = HTTPBearer()
logger = get_logger(__name__)


class AuthenticationError(Exception):
    """Exception raised when authentication fails."""
    pass


def create_access_token(user_id: str, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)

    to_encode = {"sub": user_id, "exp": expire}
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt


def verify_token(token: str) -> str:
    """Verify JWT token and return user_id."""
    # Development mode: accept hardcoded dev token
    if settings.environment == "development" and token == "dev-test-token":
        return "dev-user-id"

    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise AuthenticationError("Invalid token: missing user_id")
        return user_id
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("Token has expired")
    except PyJWTError:
        raise AuthenticationError("Invalid token")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> UserModel:
    """Dependency to get current authenticated user.

    Returns the full User object from database, or creates a dev user in development mode.
    """
    try:
        user_id = verify_token(credentials.credentials)

        # For development mode with dev-test-token, create/return a dev user
        if settings.environment == "development" and user_id == "dev-user-id":
            # Check if dev user exists
            result = await db.execute(
                select(UserModel).where(UserModel.user_id == user_id)
            )
            user = result.scalar_one_or_none()

            if not user:
                # Create dev user with free tier
                user = UserModel(
                    user_id=user_id,
                    email="dev@example.com",
                    hashed_password="dev_password_hash",
                    tier="free",
                    full_name="Dev User",
                    is_active=True,
                    is_verified=True
                )
                db.add(user)
                await db.commit()
                await db.refresh(user)

            return user

        # Look up user in database
        result = await db.execute(
            select(UserModel).where(UserModel.user_id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            raise AuthenticationError(f"User {user_id} not found")

        if not user.is_active:
            raise AuthenticationError("User account is inactive")

        return user

    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


# Optional dependency for routes that don't require authentication
async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: AsyncSession = Depends(get_db)
) -> Optional[UserModel]:
    """Optional dependency to get current user if authenticated."""
    if not credentials:
        return None

    try:
        user_id = verify_token(credentials.credentials)

        # For development mode with dev-test-token
        if settings.environment == "development" and user_id == "dev-user-id":
            result = await db.execute(
                select(UserModel).where(UserModel.user_id == user_id)
            )
            return result.scalar_one_or_none()

        # Look up user in database
        result = await db.execute(
            select(UserModel).where(UserModel.user_id == user_id)
        )
        user = result.scalar_one_or_none()

        if user and user.is_active:
            return user

        return None
    except AuthenticationError:
        return None


class UserPopulationMiddleware(BaseHTTPMiddleware):
    """Middleware to populate request.state.user for rate limiting.

    This middleware extracts the user from the Authorization header and
    populates request.state.user so that downstream middleware (like rate
    limiting) can access it without requiring authentication.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Populate request.state.user if Authorization header is present."""

        # Initialize user as None
        request.state.user = None

        # Check for Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return await call_next(request)

        # Extract token
        token = auth_header.replace("Bearer ", "")

        try:
            # Verify token
            user_id = verify_token(token)

            # Get database session
            from ..core.database import db_manager
            async with db_manager.get_session() as db:
                # For development mode with dev-test-token
                if settings.environment == "development" and user_id == "dev-user-id":
                    result = await db.execute(
                        select(UserModel).where(UserModel.user_id == user_id)
                    )
                    user = result.scalar_one_or_none()

                    if not user:
                        # Create dev user
                        user = UserModel(
                            user_id=user_id,
                            email="dev@example.com",
                            hashed_password="dev_password_hash",
                            tier="free",
                            full_name="Dev User",
                            is_active=True,
                            is_verified=True
                        )
                        db.add(user)
                        await db.commit()
                        await db.refresh(user)

                    request.state.user = user
                else:
                    # Look up user in database
                    result = await db.execute(
                        select(UserModel).where(UserModel.user_id == user_id)
                    )
                    user = result.scalar_one_or_none()

                    if user and user.is_active:
                        request.state.user = user

        except Exception:
            # If anything fails, just continue without user (fail gracefully)
            pass

        return await call_next(request)