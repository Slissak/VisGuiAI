"""Authentication API endpoints for user registration, login, and profile management."""

import re
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.middleware import create_access_token, get_current_user
from ..core.database import get_db
from ..models.user import UserModel, UserTier

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Router configuration
router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


# ============================================================================
# Pydantic Models
# ============================================================================


class RegisterRequest(BaseModel):
    """Request model for user registration.

    Attributes:
        email: User's email address (must be valid email format)
        password: User's password (min 8 chars, 1 uppercase, 1 lowercase, 1 number)
        full_name: User's full name (optional)

    Example:
        {
            "email": "user@example.com",
            "password": "SecurePass123",
            "full_name": "John Doe"
        }
    """

    email: EmailStr
    password: str
    full_name: str | None = None

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Validate password meets strength requirements.

        Requirements:
            - Minimum 8 characters
            - At least 1 uppercase letter
            - At least 1 lowercase letter
            - At least 1 number

        Args:
            v: Password string to validate

        Returns:
            The validated password

        Raises:
            ValueError: If password doesn't meet requirements
        """
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one number")
        return v


class LoginRequest(BaseModel):
    """Request model for user login.

    Attributes:
        email: User's email address
        password: User's password

    Example:
        {
            "email": "user@example.com",
            "password": "SecurePass123"
        }
    """

    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """Response model for user information.

    Attributes:
        user_id: Unique user identifier
        email: User's email address
        full_name: User's full name
        tier: User's subscription tier (free, basic, professional, enterprise)
        is_active: Whether the user account is active
        is_verified: Whether the user's email is verified
        created_at: Timestamp of account creation

    Example:
        {
            "user_id": "550e8400-e29b-41d4-a716-446655440000",
            "email": "user@example.com",
            "full_name": "John Doe",
            "tier": "free",
            "is_active": true,
            "is_verified": false,
            "created_at": "2024-01-15T10:30:00Z"
        }
    """

    user_id: str
    email: str
    full_name: str | None
    tier: str
    is_active: bool
    is_verified: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class LoginResponse(BaseModel):
    """Response model for successful login.

    Attributes:
        access_token: JWT access token for authentication
        token_type: Type of token (always "bearer")
        user: User information

    Example:
        {
            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "token_type": "bearer",
            "user": {
                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                "email": "user@example.com",
                "full_name": "John Doe",
                "tier": "free",
                "is_active": true,
                "is_verified": false,
                "created_at": "2024-01-15T10:30:00Z"
            }
        }
    """

    access_token: str
    token_type: str
    user: UserResponse


class LogoutResponse(BaseModel):
    """Response model for logout.

    Attributes:
        message: Success message

    Example:
        {
            "message": "Successfully logged out"
        }
    """

    message: str


# ============================================================================
# Helper Functions
# ============================================================================


def hash_password(password: str) -> str:
    """Hash a password using bcrypt.

    Args:
        password: Plain text password to hash

    Returns:
        Hashed password string
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash.

    Args:
        plain_password: Plain text password to verify
        hashed_password: Hashed password to compare against

    Returns:
        True if password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


async def get_user_by_email(db: AsyncSession, email: str) -> UserModel | None:
    """Get a user by email address.

    Args:
        db: Database session
        email: Email address to search for

    Returns:
        User model if found, None otherwise
    """
    result = await db.execute(select(UserModel).where(UserModel.email == email))
    return result.scalar_one_or_none()


async def create_user(
    db: AsyncSession, email: str, password: str, full_name: str | None = None
) -> UserModel:
    """Create a new user account.

    Args:
        db: Database session
        email: User's email address
        password: User's plain text password (will be hashed)
        full_name: User's full name (optional)

    Returns:
        Created user model

    Raises:
        HTTPException: If email already exists
    """
    # Check if user already exists
    existing_user = await get_user_by_email(db, email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )

    # Create new user
    user = UserModel(
        user_id=str(uuid.uuid4()),
        email=email,
        hashed_password=hash_password(password),
        full_name=full_name,
        tier=UserTier.FREE.value,
        is_active=True,
        is_verified=False,
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    return user


async def authenticate_user(
    db: AsyncSession, email: str, password: str
) -> UserModel | None:
    """Authenticate a user by email and password.

    Args:
        db: Database session
        email: User's email address
        password: User's plain text password

    Returns:
        User model if authentication successful, None otherwise
    """
    user = await get_user_by_email(db, email)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


# ============================================================================
# API Endpoints
# ============================================================================


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
    responses={
        201: {
            "description": "User successfully registered",
            "content": {
                "application/json": {
                    "example": {
                        "user_id": "550e8400-e29b-41d4-a716-446655440000",
                        "email": "user@example.com",
                        "full_name": "John Doe",
                        "tier": "free",
                        "is_active": True,
                        "is_verified": False,
                        "created_at": "2024-01-15T10:30:00Z",
                    }
                }
            },
        },
        400: {
            "description": "Email already registered",
            "content": {
                "application/json": {"example": {"detail": "Email already registered"}}
            },
        },
        422: {
            "description": "Validation error (invalid email or weak password)",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "type": "value_error",
                                "loc": ["body", "password"],
                                "msg": "Password must be at least 8 characters long",
                            }
                        ]
                    }
                }
            },
        },
    },
)
async def register(
    request: RegisterRequest, db: AsyncSession = Depends(get_db)
) -> UserResponse:
    """Register a new user account.

    Creates a new user with the provided email and password. The password will be
    securely hashed before storage. Users start with a 'free' tier and must verify
    their email before accessing certain features.

    Password Requirements:
        - Minimum 8 characters
        - At least 1 uppercase letter
        - At least 1 lowercase letter
        - At least 1 number

    Args:
        request: Registration request containing email, password, and optional full_name
        db: Database session (injected)

    Returns:
        User information (without authentication token - user must login)

    Raises:
        HTTPException 400: If email is already registered
        HTTPException 422: If validation fails (invalid email or weak password)
    """
    user = await create_user(
        db=db,
        email=request.email,
        password=request.password,
        full_name=request.full_name,
    )

    return UserResponse.model_validate(user)


@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="Login with email and password",
    responses={
        200: {
            "description": "Successfully authenticated",
            "content": {
                "application/json": {
                    "example": {
                        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                        "token_type": "bearer",
                        "user": {
                            "user_id": "550e8400-e29b-41d4-a716-446655440000",
                            "email": "user@example.com",
                            "full_name": "John Doe",
                            "tier": "free",
                            "is_active": True,
                            "is_verified": False,
                            "created_at": "2024-01-15T10:30:00Z",
                        },
                    }
                }
            },
        },
        401: {
            "description": "Invalid credentials",
            "content": {
                "application/json": {
                    "example": {"detail": "Incorrect email or password"}
                }
            },
        },
        403: {
            "description": "User account is not active",
            "content": {
                "application/json": {"example": {"detail": "User account is inactive"}}
            },
        },
    },
)
async def login(
    request: LoginRequest, db: AsyncSession = Depends(get_db)
) -> LoginResponse:
    """Login with email and password to obtain an access token.

    Authenticates the user with their email and password. On success, returns a JWT
    access token that can be used to authenticate subsequent requests, along with
    the user's profile information.

    The access token should be included in the Authorization header of protected
    endpoints as: "Authorization: Bearer <token>"

    Args:
        request: Login request containing email and password
        db: Database session (injected)

    Returns:
        Login response containing access token and user information

    Raises:
        HTTPException 401: If credentials are invalid
        HTTPException 403: If user account is not active
    """
    # Authenticate user
    user = await authenticate_user(db, request.email, request.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="User account is inactive"
        )

    # Update last login timestamp
    await db.execute(
        update(UserModel)
        .where(UserModel.user_id == user.user_id)
        .values(last_login_at=datetime.utcnow())
    )
    await db.commit()

    # Refresh user to get updated last_login_at
    await db.refresh(user)

    # Generate access token
    access_token = create_access_token(user_id=user.user_id)

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current user profile",
    responses={
        200: {
            "description": "Current user's profile information",
            "content": {
                "application/json": {
                    "example": {
                        "user_id": "550e8400-e29b-41d4-a716-446655440000",
                        "email": "user@example.com",
                        "full_name": "John Doe",
                        "tier": "free",
                        "is_active": True,
                        "is_verified": False,
                        "created_at": "2024-01-15T10:30:00Z",
                    }
                }
            },
        },
        401: {
            "description": "Not authenticated or invalid token",
            "content": {"application/json": {"example": {"detail": "Invalid token"}}},
        },
    },
)
async def get_current_user_profile(
    current_user: UserModel = Depends(get_current_user),
) -> UserResponse:
    """Get the current authenticated user's profile information.

    Returns the profile information for the currently authenticated user.
    Requires a valid JWT access token in the Authorization header.

    Authorization:
        Requires: Bearer token in Authorization header
        Example: "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

    Args:
        current_user: Currently authenticated user (injected from token)

    Returns:
        Current user's profile information

    Raises:
        HTTPException 401: If not authenticated or token is invalid
    """
    return UserResponse.model_validate(current_user)


@router.post(
    "/logout",
    response_model=LogoutResponse,
    status_code=status.HTTP_200_OK,
    summary="Logout current user",
    responses={
        200: {
            "description": "Successfully logged out",
            "content": {
                "application/json": {"example": {"message": "Successfully logged out"}}
            },
        }
    },
)
async def logout() -> LogoutResponse:
    """Logout the current user.

    Since JWT tokens are stateless, this endpoint simply returns a success message.
    The client should discard the access token on their side.

    In a future implementation, this could be enhanced with:
        - Token blacklisting in Redis
        - Revocation list
        - Short-lived tokens with refresh token rotation

    Returns:
        Success message indicating logout was processed

    Note:
        The client is responsible for removing the JWT token from storage.
        The token will remain valid until it expires unless a blacklist is implemented.
    """
    return LogoutResponse(message="Successfully logged out")
