"""Admin API endpoints for user management, abuse detection, and system monitoring."""

from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.sql.expression import cast
from sqlalchemy.types import Date

from ..core.database import get_db
from ..models.user import UserModel, UserTier
from ..shared.db.models.usage import UserUsage
from ..models.session import UserSessionModel
from ..auth.admin import require_admin
from ..services.abuse_detection import AbuseDetectionService
from ..utils.logging import get_logger

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])
logger = get_logger(__name__)


# ==================== Request/Response Models ====================

class UserListResponse(BaseModel):
    """Response model for user listing."""
    user_id: str
    email: str
    tier: str
    full_name: Optional[str]
    is_active: bool
    is_verified: bool
    is_admin: bool
    created_at: datetime
    last_login_at: Optional[datetime]

    class Config:
        from_attributes = True


class UserDetailResponse(BaseModel):
    """Response model for detailed user information."""
    user_id: str
    email: str
    tier: str
    full_name: Optional[str]
    is_active: bool
    is_verified: bool
    is_admin: bool
    created_at: datetime
    updated_at: datetime
    last_login_at: Optional[datetime]

    # Usage information
    daily_cost: float
    daily_requests: int
    monthly_cost: float
    monthly_requests: int
    daily_budget_exceeded: bool
    monthly_budget_exceeded: bool

    # Session count
    total_sessions: int
    active_sessions: int

    class Config:
        from_attributes = True


class UsageStatsResponse(BaseModel):
    """Response model for usage statistics."""
    user_id: str
    email: str
    tier: str
    daily_cost: float
    daily_requests: int
    monthly_cost: float
    monthly_requests: int
    last_daily_reset: datetime
    last_monthly_reset: datetime


class UpdateUserTierRequest(BaseModel):
    """Request model for updating user tier."""
    tier: str = Field(..., description="New tier (free, basic, professional, enterprise)")


class BlockUserRequest(BaseModel):
    """Request model for blocking/unblocking a user."""
    reason: Optional[str] = Field(None, description="Reason for blocking the user")


class AbuseAlertResponse(BaseModel):
    """Response model for abuse alerts."""
    user_id: str
    email: str
    violations: List[str]
    timestamp: str


class SystemStatsResponse(BaseModel):
    """Response model for system statistics."""
    total_users: int
    active_users_today: int
    active_users_this_week: int
    users_by_tier: dict
    total_sessions_today: int
    total_requests_today: int
    total_cost_today: float
    total_cost_this_month: float
    average_cost_per_user: float


class UserSearchResponse(BaseModel):
    """Response model for user search results."""
    users: List[UserListResponse]
    total: int
    page: int
    page_size: int


# ==================== Admin Endpoints ====================

@router.get("/users", response_model=UserSearchResponse)
async def list_users(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    tier: Optional[str] = Query(None, description="Filter by tier"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    is_admin: Optional[bool] = Query(None, description="Filter by admin status"),
    search: Optional[str] = Query(None, description="Search by email or name"),
    db: AsyncSession = Depends(get_db),
    admin_user: UserModel = Depends(require_admin)
):
    """List all users with pagination and filtering.

    Requires admin access.
    """
    logger.info(
        "admin_list_users",
        admin_user_id=admin_user.user_id,
        page=page,
        page_size=page_size,
        filters={"tier": tier, "is_active": is_active, "is_admin": is_admin, "search": search}
    )

    # Build query
    query = select(UserModel)

    # Apply filters
    if tier:
        query = query.where(UserModel.tier == tier)
    if is_active is not None:
        query = query.where(UserModel.is_active == is_active)
    if is_admin is not None:
        query = query.where(UserModel.is_admin == is_admin)
    if search:
        search_term = f"%{search.lower()}%"
        query = query.where(
            or_(
                func.lower(UserModel.email).like(search_term),
                func.lower(UserModel.full_name).like(search_term)
            )
        )

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    result = await db.execute(count_query)
    total = result.scalar()

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(desc(UserModel.created_at))

    # Execute query
    result = await db.execute(query)
    users = result.scalars().all()

    return UserSearchResponse(
        users=[UserListResponse.model_validate(user) for user in users],
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/users/{user_id}", response_model=UserDetailResponse)
async def get_user_details(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    admin_user: UserModel = Depends(require_admin)
):
    """Get detailed information about a specific user.

    Requires admin access.
    """
    logger.info("admin_get_user_details", admin_user_id=admin_user.user_id, target_user_id=user_id)

    # Get user
    result = await db.execute(
        select(UserModel).where(UserModel.user_id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")

    # Get usage data
    result = await db.execute(
        select(UserUsage).where(UserUsage.user_id == user_id)
    )
    usage = result.scalar_one_or_none()

    # Get session counts
    result = await db.execute(
        select(func.count(UserSessionModel.session_id))
        .where(UserSessionModel.user_id == user_id)
    )
    total_sessions = result.scalar() or 0

    result = await db.execute(
        select(func.count(UserSessionModel.session_id))
        .where(
            and_(
                UserSessionModel.user_id == user_id,
                UserSessionModel.status.in_(["in_progress", "active"])
            )
        )
    )
    active_sessions = result.scalar() or 0

    # Build response
    return UserDetailResponse(
        user_id=user.user_id,
        email=user.email,
        tier=user.tier,
        full_name=user.full_name,
        is_active=user.is_active,
        is_verified=user.is_verified,
        is_admin=user.is_admin,
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login_at=user.last_login_at,
        daily_cost=usage.daily_cost if usage else 0.0,
        daily_requests=usage.daily_requests if usage else 0,
        monthly_cost=usage.monthly_cost if usage else 0.0,
        monthly_requests=usage.monthly_requests if usage else 0,
        daily_budget_exceeded=usage.daily_budget_exceeded if usage else False,
        monthly_budget_exceeded=usage.monthly_budget_exceeded if usage else False,
        total_sessions=total_sessions,
        active_sessions=active_sessions
    )


@router.patch("/users/{user_id}/tier")
async def update_user_tier(
    user_id: str,
    request: UpdateUserTierRequest,
    db: AsyncSession = Depends(get_db),
    admin_user: UserModel = Depends(require_admin)
):
    """Update a user's tier.

    Requires admin access.
    """
    logger.info(
        "admin_update_user_tier",
        admin_user_id=admin_user.user_id,
        target_user_id=user_id,
        new_tier=request.tier
    )

    # Validate tier
    valid_tiers = [tier.value for tier in UserTier]
    if request.tier not in valid_tiers:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid tier. Must be one of: {', '.join(valid_tiers)}"
        )

    # Get user
    result = await db.execute(
        select(UserModel).where(UserModel.user_id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")

    # Update tier
    old_tier = user.tier
    user.tier = request.tier
    await db.commit()
    await db.refresh(user)

    logger.info(
        "user_tier_updated",
        admin_user_id=admin_user.user_id,
        target_user_id=user_id,
        old_tier=old_tier,
        new_tier=request.tier
    )

    return {
        "message": "User tier updated successfully",
        "user_id": user_id,
        "old_tier": old_tier,
        "new_tier": request.tier
    }


@router.post("/users/{user_id}/block")
async def block_user(
    user_id: str,
    request: BlockUserRequest,
    db: AsyncSession = Depends(get_db),
    admin_user: UserModel = Depends(require_admin)
):
    """Block a user account.

    Requires admin access.
    """
    logger.info(
        "admin_block_user",
        admin_user_id=admin_user.user_id,
        target_user_id=user_id,
        reason=request.reason
    )

    # Get user
    result = await db.execute(
        select(UserModel).where(UserModel.user_id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")

    # Prevent blocking admins
    if user.is_admin:
        raise HTTPException(
            status_code=403,
            detail="Cannot block admin users. Remove admin privileges first."
        )

    # Block user
    user.is_active = False
    await db.commit()

    logger.warning(
        "user_blocked",
        admin_user_id=admin_user.user_id,
        target_user_id=user_id,
        target_email=user.email,
        reason=request.reason
    )

    return {
        "message": "User blocked successfully",
        "user_id": user_id,
        "email": user.email,
        "reason": request.reason
    }


@router.post("/users/{user_id}/unblock")
async def unblock_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    admin_user: UserModel = Depends(require_admin)
):
    """Unblock a user account.

    Requires admin access.
    """
    logger.info("admin_unblock_user", admin_user_id=admin_user.user_id, target_user_id=user_id)

    # Get user
    result = await db.execute(
        select(UserModel).where(UserModel.user_id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")

    # Unblock user
    user.is_active = True
    await db.commit()

    logger.info(
        "user_unblocked",
        admin_user_id=admin_user.user_id,
        target_user_id=user_id,
        target_email=user.email
    )

    return {
        "message": "User unblocked successfully",
        "user_id": user_id,
        "email": user.email
    }


@router.get("/usage", response_model=List[UsageStatsResponse])
async def get_usage_stats(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    order_by: str = Query("daily_cost", description="Order by field (daily_cost, monthly_cost, daily_requests)"),
    order: str = Query("desc", description="Order direction (asc, desc)"),
    db: AsyncSession = Depends(get_db),
    admin_user: UserModel = Depends(require_admin)
):
    """Get usage statistics for all users.

    Requires admin access.
    """
    logger.info(
        "admin_get_usage_stats",
        admin_user_id=admin_user.user_id,
        page=page,
        page_size=page_size,
        order_by=order_by,
        order=order
    )

    # Build query
    query = (
        select(UserUsage, UserModel)
        .join(UserModel, UserUsage.user_id == UserModel.user_id)
    )

    # Apply ordering
    order_column = {
        "daily_cost": UserUsage.daily_cost,
        "monthly_cost": UserUsage.monthly_cost,
        "daily_requests": UserUsage.daily_requests,
        "monthly_requests": UserUsage.monthly_requests
    }.get(order_by, UserUsage.daily_cost)

    if order == "asc":
        query = query.order_by(order_column.asc())
    else:
        query = query.order_by(order_column.desc())

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    # Execute query
    result = await db.execute(query)
    rows = result.all()

    # Build response
    usage_stats = []
    for usage, user in rows:
        usage_stats.append(UsageStatsResponse(
            user_id=user.user_id,
            email=user.email,
            tier=user.tier,
            daily_cost=usage.daily_cost,
            daily_requests=usage.daily_requests,
            monthly_cost=usage.monthly_cost,
            monthly_requests=usage.monthly_requests,
            last_daily_reset=usage.last_daily_reset,
            last_monthly_reset=usage.last_monthly_reset
        ))

    return usage_stats


@router.get("/abuse-alerts", response_model=List[AbuseAlertResponse])
async def get_abuse_alerts(
    limit: int = Query(50, ge=1, le=100, description="Maximum number of alerts"),
    db: AsyncSession = Depends(get_db),
    admin_user: UserModel = Depends(require_admin)
):
    """Get recent abuse detection alerts.

    Requires admin access.
    """
    logger.info("admin_get_abuse_alerts", admin_user_id=admin_user.user_id, limit=limit)

    abuse_service = AbuseDetectionService(db)
    alerts = await abuse_service.get_recent_abuse_alerts(limit=limit)

    return [AbuseAlertResponse(**alert) for alert in alerts]


@router.post("/abuse-alerts/{user_id}/clear")
async def clear_abuse_alert(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    admin_user: UserModel = Depends(require_admin)
):
    """Clear an abuse alert after review.

    Requires admin access.
    """
    logger.info(
        "admin_clear_abuse_alert",
        admin_user_id=admin_user.user_id,
        target_user_id=user_id
    )

    abuse_service = AbuseDetectionService(db)
    await abuse_service.clear_abuse_alert(user_id)

    return {
        "message": "Abuse alert cleared",
        "user_id": user_id
    }


@router.post("/abuse-alerts/{user_id}/check")
async def check_user_for_abuse(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    admin_user: UserModel = Depends(require_admin)
):
    """Manually check a user for abuse patterns.

    Requires admin access.
    """
    logger.info(
        "admin_check_user_abuse",
        admin_user_id=admin_user.user_id,
        target_user_id=user_id
    )

    abuse_service = AbuseDetectionService(db)
    is_abuse, violations = await abuse_service.check_user_abuse(user_id)

    return {
        "user_id": user_id,
        "is_abuse_detected": is_abuse,
        "violations": violations,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }


@router.get("/stats", response_model=SystemStatsResponse)
async def get_system_stats(
    db: AsyncSession = Depends(get_db),
    admin_user: UserModel = Depends(require_admin)
):
    """Get system-wide statistics.

    Requires admin access.
    """
    logger.info("admin_get_system_stats", admin_user_id=admin_user.user_id)

    now = datetime.utcnow()
    today_start = datetime(now.year, now.month, now.day)
    week_start = now - timedelta(days=7)
    month_start = datetime(now.year, now.month, 1)

    # Total users
    result = await db.execute(select(func.count(UserModel.user_id)))
    total_users = result.scalar() or 0

    # Active users today (users who logged in today)
    result = await db.execute(
        select(func.count(UserModel.user_id))
        .where(UserModel.last_login_at >= today_start)
    )
    active_users_today = result.scalar() or 0

    # Active users this week
    result = await db.execute(
        select(func.count(UserModel.user_id))
        .where(UserModel.last_login_at >= week_start)
    )
    active_users_this_week = result.scalar() or 0

    # Users by tier
    result = await db.execute(
        select(UserModel.tier, func.count(UserModel.user_id))
        .group_by(UserModel.tier)
    )
    users_by_tier = {tier: count for tier, count in result.all()}

    # Total sessions today
    result = await db.execute(
        select(func.count(UserSessionModel.session_id))
        .where(UserSessionModel.created_at >= today_start)
    )
    total_sessions_today = result.scalar() or 0

    # Total requests today (sum of daily_requests)
    result = await db.execute(
        select(func.sum(UserUsage.daily_requests))
    )
    total_requests_today = result.scalar() or 0

    # Total cost today
    result = await db.execute(
        select(func.sum(UserUsage.daily_cost))
    )
    total_cost_today = result.scalar() or 0.0

    # Total cost this month
    result = await db.execute(
        select(func.sum(UserUsage.monthly_cost))
    )
    total_cost_this_month = result.scalar() or 0.0

    # Average cost per user
    average_cost_per_user = total_cost_today / total_users if total_users > 0 else 0.0

    return SystemStatsResponse(
        total_users=total_users,
        active_users_today=active_users_today,
        active_users_this_week=active_users_this_week,
        users_by_tier=users_by_tier,
        total_sessions_today=total_sessions_today,
        total_requests_today=total_requests_today,
        total_cost_today=total_cost_today,
        total_cost_this_month=total_cost_this_month,
        average_cost_per_user=average_cost_per_user
    )
