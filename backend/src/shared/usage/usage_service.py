"""Service for managing user token usage and limits."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from uuid import UUID
from datetime import datetime

from src.shared.db.models.usage import UserUsage


class UsageService:
    """Service for managing user token usage and quota enforcement."""

    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def get_or_create_usage(self, user_id: UUID) -> UserUsage:
        """Get the usage record for a user, creating one if it doesn't exist."""
        result = await self.db.execute(
            select(UserUsage).filter(UserUsage.user_id == user_id)
        )
        usage = result.scalars().first()

        if not usage:
            usage = UserUsage(user_id=user_id)
            self.db.add(usage)
            await self.db.commit()
            await self.db.refresh(usage)

        return usage

    async def check_limits(self, user_id: UUID, daily_budget: float, monthly_budget: float) -> tuple[bool, str]:
        """
        Check if a user has exceeded their daily or monthly budget.

        Args:
            user_id: User's UUID
            daily_budget: User's daily budget limit
            monthly_budget: User's monthly budget limit

        Returns:
            Tuple of (is_within_limits, error_message)
        """
        usage = await self.get_or_create_usage(user_id)

        # Reset daily/monthly counters if needed
        await self.reset_counters_if_needed(usage)

        # Check daily limit
        if usage.daily_cost >= daily_budget:
            usage.daily_budget_exceeded = True
            await self.db.commit()
            return False, f"Daily budget exceeded ({usage.daily_cost:.4f} / {daily_budget:.4f})"

        # Check monthly limit
        if usage.monthly_cost >= monthly_budget:
            usage.monthly_budget_exceeded = True
            await self.db.commit()
            return False, f"Monthly budget exceeded ({usage.monthly_cost:.4f} / {monthly_budget:.4f})"

        return True, ""

    async def increment_usage(self, user_id: UUID, cost: float):
        """
        Increment the usage for a user.

        Args:
            user_id: User's UUID
            cost: Cost of the operation in USD
        """
        usage = await self.get_or_create_usage(user_id)
        usage.daily_cost += cost
        usage.monthly_cost += cost
        usage.daily_requests += 1
        usage.monthly_requests += 1
        await self.db.commit()

    async def get_usage_stats(self, user_id: UUID) -> dict:
        """
        Get current usage statistics for a user.

        Returns:
            Dictionary with daily and monthly stats
        """
        usage = await self.get_or_create_usage(user_id)
        await self.reset_counters_if_needed(usage)

        return {
            "daily": {
                "cost": usage.daily_cost,
                "requests": usage.daily_requests,
                "reset_date": usage.daily_reset_date.isoformat(),
                "budget_exceeded": usage.daily_budget_exceeded,
            },
            "monthly": {
                "cost": usage.monthly_cost,
                "requests": usage.monthly_requests,
                "reset_date": usage.monthly_reset_date.isoformat(),
                "budget_exceeded": usage.monthly_budget_exceeded,
            },
        }

    async def reset_counters_if_needed(self, usage: UserUsage):
        """Reset daily and monthly counters if the reset date has passed."""
        now = datetime.utcnow()
        needs_commit = False

        # Reset daily if date has passed
        if now.date() > usage.daily_reset_date.date():
            usage.daily_cost = 0.0
            usage.daily_requests = 0
            usage.daily_budget_exceeded = False
            usage.daily_reset_date = now
            needs_commit = True

        # Reset monthly if month/year has passed
        if now.month > usage.monthly_reset_date.month or now.year > usage.monthly_reset_date.year:
            usage.monthly_cost = 0.0
            usage.monthly_requests = 0
            usage.monthly_budget_exceeded = False
            usage.monthly_reset_date = now
            needs_commit = True

        if needs_commit:
            await self.db.commit()
