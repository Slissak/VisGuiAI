"""Admin authorization middleware and dependencies."""

from fastapi import HTTPException, status, Depends

from ..models.user import UserModel
from .middleware import get_current_user
from ..utils.logging import get_logger

logger = get_logger(__name__)


class AdminAuthorizationError(Exception):
    """Exception raised when admin authorization fails."""
    pass


async def require_admin(current_user: UserModel = Depends(get_current_user)) -> UserModel:
    """Dependency to require admin access.

    This dependency should be used on admin-only endpoints to ensure
    the authenticated user has admin privileges.

    Args:
        current_user: The currently authenticated user

    Returns:
        UserModel: The authenticated admin user

    Raises:
        HTTPException: If user is not an admin (403 Forbidden)
    """
    if not current_user.is_admin:
        logger.warning(
            "admin_access_denied",
            user_id=current_user.user_id,
            email=current_user.email,
            tier=current_user.tier
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required. You do not have permission to access this resource."
        )

    logger.info(
        "admin_access_granted",
        user_id=current_user.user_id,
        email=current_user.email
    )

    return current_user
