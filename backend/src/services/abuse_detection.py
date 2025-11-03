"""Abuse detection service for monitoring and alerting on suspicious activity."""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from sqlalchemy.sql.expression import cast
from sqlalchemy.types import Date

from ..models.user import UserModel
from ..shared.db.models.usage import UserUsage
from ..models.session import UserSessionModel
from ..utils.logging import get_logger
from ..core.redis import redis_manager

logger = get_logger(__name__)


class AbuseMetrics:
    """Container for abuse detection metrics."""

    def __init__(
        self,
        user_id: str,
        requests_per_hour: int,
        unique_ips_per_day: int,
        failed_requests_per_hour: int,
        cost_spike_ratio: float,
        session_count_per_day: int
    ):
        self.user_id = user_id
        self.requests_per_hour = requests_per_hour
        self.unique_ips_per_day = unique_ips_per_day
        self.failed_requests_per_hour = failed_requests_per_hour
        self.cost_spike_ratio = cost_spike_ratio
        self.session_count_per_day = session_count_per_day


class AbuseDetectionService:
    """Service for detecting and alerting on abuse patterns."""

    # Thresholds for abuse detection
    THRESHOLDS = {
        "free": {
            "requests_per_hour": 50,
            "unique_ips_per_day": 3,
            "failed_requests_per_hour": 20,
            "cost_spike_ratio": 3.0,  # 3x average daily cost
            "session_count_per_day": 20
        },
        "basic": {
            "requests_per_hour": 150,
            "unique_ips_per_day": 5,
            "failed_requests_per_hour": 50,
            "cost_spike_ratio": 4.0,
            "session_count_per_day": 50
        },
        "professional": {
            "requests_per_hour": 300,
            "unique_ips_per_day": 10,
            "failed_requests_per_hour": 100,
            "cost_spike_ratio": 5.0,
            "session_count_per_day": 100
        },
        "enterprise": {
            "requests_per_hour": 1000,
            "unique_ips_per_day": 50,
            "failed_requests_per_hour": 200,
            "cost_spike_ratio": 10.0,
            "session_count_per_day": 500
        }
    }

    def __init__(self, db: AsyncSession):
        self.db = db

    async def check_user_abuse(self, user_id: str) -> Tuple[bool, List[str]]:
        """Check if a user is exhibiting abuse patterns.

        Returns:
            Tuple of (is_abuse_detected, list_of_violations)
        """
        # Get user
        result = await self.db.execute(
            select(UserModel).where(UserModel.user_id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            logger.warning("abuse_check_user_not_found", user_id=user_id)
            return False, []

        # Get thresholds for user tier
        thresholds = self.THRESHOLDS.get(user.tier, self.THRESHOLDS["free"])

        # Collect metrics
        metrics = await self._collect_metrics(user_id)

        # Check each threshold
        violations = []

        if metrics.requests_per_hour > thresholds["requests_per_hour"]:
            violations.append(
                f"Excessive requests per hour: {metrics.requests_per_hour} > {thresholds['requests_per_hour']}"
            )

        if metrics.unique_ips_per_day > thresholds["unique_ips_per_day"]:
            violations.append(
                f"Multiple IPs per day: {metrics.unique_ips_per_day} > {thresholds['unique_ips_per_day']}"
            )

        if metrics.failed_requests_per_hour > thresholds["failed_requests_per_hour"]:
            violations.append(
                f"Excessive failed requests: {metrics.failed_requests_per_hour} > {thresholds['failed_requests_per_hour']}"
            )

        if metrics.cost_spike_ratio > thresholds["cost_spike_ratio"]:
            violations.append(
                f"Cost spike detected: {metrics.cost_spike_ratio:.2f}x average > {thresholds['cost_spike_ratio']}x"
            )

        if metrics.session_count_per_day > thresholds["session_count_per_day"]:
            violations.append(
                f"Excessive sessions per day: {metrics.session_count_per_day} > {thresholds['session_count_per_day']}"
            )

        is_abuse = len(violations) > 0

        if is_abuse:
            logger.warning(
                "abuse_detected",
                user_id=user_id,
                tier=user.tier,
                email=user.email,
                violations=violations
            )
            # Store abuse alert in Redis for admin dashboard
            await self._store_abuse_alert(user_id, user.email, violations)

        return is_abuse, violations

    async def _collect_metrics(self, user_id: str) -> AbuseMetrics:
        """Collect abuse detection metrics for a user."""
        now = datetime.utcnow()
        one_hour_ago = now - timedelta(hours=1)
        one_day_ago = now - timedelta(days=1)
        seven_days_ago = now - timedelta(days=7)

        # Get requests per hour (from Redis rate limiter)
        requests_per_hour = await self._get_requests_per_hour(user_id)

        # Get unique IPs per day (from Redis if tracked)
        unique_ips_per_day = await self._get_unique_ips_per_day(user_id)

        # Get failed requests per hour (from Redis if tracked)
        failed_requests_per_hour = await self._get_failed_requests_per_hour(user_id)

        # Get cost spike ratio (current daily cost vs 7-day average)
        cost_spike_ratio = await self._get_cost_spike_ratio(user_id)

        # Get session count per day
        result = await self.db.execute(
            select(func.count(UserSessionModel.session_id))
            .where(
                and_(
                    UserSessionModel.user_id == user_id,
                    UserSessionModel.created_at >= one_day_ago
                )
            )
        )
        session_count_per_day = result.scalar() or 0

        return AbuseMetrics(
            user_id=user_id,
            requests_per_hour=requests_per_hour,
            unique_ips_per_day=unique_ips_per_day,
            failed_requests_per_hour=failed_requests_per_hour,
            cost_spike_ratio=cost_spike_ratio,
            session_count_per_day=session_count_per_day
        )

    async def _get_requests_per_hour(self, user_id: str) -> int:
        """Get request count from Redis rate limiter."""
        if not redis_manager.is_available:
            return 0

        try:
            key = f"rate_limit:user:{user_id}:per_minute"
            count = await redis_manager.client.zcard(key)
            # Multiply by 60 to estimate hourly rate from per-minute window
            return count * 60
        except Exception as e:
            logger.error("abuse_metrics_redis_error", error=str(e), metric="requests_per_hour")
            return 0

    async def _get_unique_ips_per_day(self, user_id: str) -> int:
        """Get unique IP count from Redis."""
        if not redis_manager.is_available:
            return 0

        try:
            key = f"user_ips:{user_id}:daily"
            count = await redis_manager.client.scard(key)
            return count
        except Exception as e:
            logger.error("abuse_metrics_redis_error", error=str(e), metric="unique_ips")
            return 0

    async def _get_failed_requests_per_hour(self, user_id: str) -> int:
        """Get failed request count from Redis."""
        if not redis_manager.is_available:
            return 0

        try:
            key = f"failed_requests:{user_id}:hourly"
            count = await redis_manager.client.get(key)
            return int(count) if count else 0
        except Exception as e:
            logger.error("abuse_metrics_redis_error", error=str(e), metric="failed_requests")
            return 0

    async def _get_cost_spike_ratio(self, user_id: str) -> float:
        """Calculate cost spike ratio (today's cost vs 7-day average)."""
        try:
            # Get current usage
            result = await self.db.execute(
                select(UserUsage).where(UserUsage.user_id == user_id)
            )
            usage = result.scalar_one_or_none()

            if not usage or usage.daily_cost == 0:
                return 0.0

            # Get 7-day average cost
            seven_days_ago = datetime.utcnow() - timedelta(days=7)
            result = await self.db.execute(
                select(func.avg(UserUsage.daily_cost))
                .where(
                    and_(
                        UserUsage.user_id == user_id,
                        UserUsage.last_daily_reset >= seven_days_ago
                    )
                )
            )
            avg_cost = result.scalar() or usage.daily_cost

            if avg_cost == 0:
                return 0.0

            return usage.daily_cost / avg_cost
        except Exception as e:
            logger.error("abuse_metrics_db_error", error=str(e), metric="cost_spike")
            return 0.0

    async def _store_abuse_alert(self, user_id: str, email: str, violations: List[str]):
        """Store abuse alert in Redis for admin dashboard."""
        if not redis_manager.is_available:
            return

        try:
            alert_key = f"abuse_alerts:{user_id}"
            alert_data = {
                "user_id": user_id,
                "email": email,
                "violations": ",".join(violations),
                "timestamp": datetime.utcnow().isoformat()
            }

            # Store alert with 7-day expiration
            await redis_manager.client.hset(alert_key, mapping=alert_data)
            await redis_manager.client.expire(alert_key, 7 * 24 * 60 * 60)

            # Add to sorted set for dashboard listing
            await redis_manager.client.zadd(
                "abuse_alerts:list",
                {user_id: datetime.utcnow().timestamp()}
            )

            logger.info("abuse_alert_stored", user_id=user_id, email=email)
        except Exception as e:
            logger.error("abuse_alert_storage_error", error=str(e), user_id=user_id)

    async def get_recent_abuse_alerts(self, limit: int = 50) -> List[Dict]:
        """Get recent abuse alerts for admin dashboard."""
        if not redis_manager.is_available:
            return []

        try:
            # Get most recent user IDs from sorted set
            user_ids = await redis_manager.client.zrevrange("abuse_alerts:list", 0, limit - 1)

            alerts = []
            for user_id in user_ids:
                alert_key = f"abuse_alerts:{user_id}"
                alert_data = await redis_manager.client.hgetall(alert_key)

                if alert_data:
                    alerts.append({
                        "user_id": alert_data.get("user_id", ""),
                        "email": alert_data.get("email", ""),
                        "violations": alert_data.get("violations", "").split(","),
                        "timestamp": alert_data.get("timestamp", "")
                    })

            return alerts
        except Exception as e:
            logger.error("abuse_alerts_fetch_error", error=str(e))
            return []

    async def clear_abuse_alert(self, user_id: str):
        """Clear abuse alert for a user (after admin review)."""
        if not redis_manager.is_available:
            return

        try:
            alert_key = f"abuse_alerts:{user_id}"
            await redis_manager.client.delete(alert_key)
            await redis_manager.client.zrem("abuse_alerts:list", user_id)

            logger.info("abuse_alert_cleared", user_id=user_id)
        except Exception as e:
            logger.error("abuse_alert_clear_error", error=str(e), user_id=user_id)

    async def track_ip_for_user(self, user_id: str, ip_address: str):
        """Track IP address for a user (for multiple IP detection)."""
        if not redis_manager.is_available:
            return

        try:
            key = f"user_ips:{user_id}:daily"
            await redis_manager.client.sadd(key, ip_address)
            # Expire at end of day (24 hours)
            await redis_manager.client.expire(key, 24 * 60 * 60)
        except Exception as e:
            logger.error("ip_tracking_error", error=str(e), user_id=user_id)

    async def track_failed_request(self, user_id: str):
        """Track failed request for a user."""
        if not redis_manager.is_available:
            return

        try:
            key = f"failed_requests:{user_id}:hourly"
            await redis_manager.client.incr(key)
            # Expire after 1 hour
            await redis_manager.client.expire(key, 60 * 60)
        except Exception as e:
            logger.error("failed_request_tracking_error", error=str(e), user_id=user_id)
