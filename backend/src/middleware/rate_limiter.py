"""Rate limiting middleware with Redis backend and tier-based limits."""

import time
from typing import Optional, Callable, Dict, Tuple
from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from ..core.redis import redis_manager
from ..models.user import UserTier
from ..utils.logging import get_logger

logger = get_logger(__name__)


class RateLimitExceeded(HTTPException):
    """Exception raised when rate limit is exceeded."""

    def __init__(self, detail: str, retry_after: int):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail,
            headers={"Retry-After": str(retry_after)}
        )


class RateLimiter:
    """Redis-backed rate limiter with sliding window algorithm."""

    def __init__(self):
        self.redis = redis_manager
        logger.info("RateLimiter initialized with Redis backend")

    async def check_rate_limit(
        self,
        key: str,
        max_requests: int,
        window_seconds: int
    ) -> Tuple[bool, int, int]:
        """Check if rate limit is exceeded using sliding window.

        Args:
            key: Unique identifier for rate limit (e.g., "user:123:per_minute")
            max_requests: Maximum number of requests allowed in window
            window_seconds: Time window in seconds

        Returns:
            Tuple of (is_allowed, current_count, retry_after_seconds)
        """
        if not self.redis.is_available:
            # If Redis is unavailable, allow the request (fail open)
            logger.warning("rate_limit_redis_unavailable", key=key)
            return True, 0, 0

        try:
            current_time = time.time()
            window_start = current_time - window_seconds

            # Redis key for this rate limit
            redis_key = f"rate_limit:{key}"

            # Use Redis sorted set with timestamps as scores
            pipe = self.redis.client.pipeline()

            # Remove old entries outside the current window
            pipe.zremrangebyscore(redis_key, 0, window_start)

            # Count requests in current window
            pipe.zcard(redis_key)

            # Add current request with current timestamp
            pipe.zadd(redis_key, {str(current_time): current_time})

            # Set expiration on the key (cleanup)
            pipe.expire(redis_key, window_seconds + 1)

            # Execute pipeline
            results = await pipe.execute()

            # Get current count (before adding this request)
            current_count = results[1]

            if current_count >= max_requests:
                # Get the oldest request in the window
                oldest = await self.redis.client.zrange(redis_key, 0, 0, withscores=True)
                if oldest:
                    oldest_timestamp = oldest[0][1]
                    retry_after = int(oldest_timestamp + window_seconds - current_time) + 1
                else:
                    retry_after = window_seconds

                logger.warning(
                    "rate_limit_exceeded",
                    key=key,
                    current_count=current_count,
                    max_requests=max_requests,
                    retry_after=retry_after
                )
                return False, current_count, retry_after

            logger.debug(
                "rate_limit_check",
                key=key,
                current_count=current_count + 1,
                max_requests=max_requests
            )
            return True, current_count + 1, 0

        except Exception as e:
            # If Redis operation fails, log and allow the request (fail open)
            logger.error(
                "rate_limit_check_failed",
                error=str(e),
                error_type=type(e).__name__,
                key=key
            )
            return True, 0, 0

    async def get_current_usage(self, key: str, window_seconds: int) -> int:
        """Get current usage count for a rate limit key.

        Args:
            key: Rate limit key
            window_seconds: Time window in seconds

        Returns:
            Current request count in the window
        """
        if not self.redis.is_available:
            return 0

        try:
            current_time = time.time()
            window_start = current_time - window_seconds
            redis_key = f"rate_limit:{key}"

            # Count requests in current window
            count = await self.redis.client.zcount(redis_key, window_start, current_time)
            return count
        except Exception as e:
            logger.error(
                "get_current_usage_failed",
                error=str(e),
                key=key
            )
            return 0


class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for rate limiting based on user tier."""

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.rate_limiter = RateLimiter()

        # Tier-based rate limits (requests per window)
        self.tier_limits = {
            UserTier.FREE.value: {
                "per_minute": 10,
                "per_hour": 100,
                "per_day": 1000,
            },
            UserTier.BASIC.value: {
                "per_minute": 30,
                "per_hour": 500,
                "per_day": 5000,
            },
            UserTier.PROFESSIONAL.value: {
                "per_minute": 60,
                "per_hour": 2000,
                "per_day": 20000,
            },
            UserTier.ENTERPRISE.value: {
                "per_minute": 300,
                "per_hour": 10000,
                "per_day": 100000,
            },
        }

        # Window sizes in seconds
        self.windows = {
            "per_minute": 60,
            "per_hour": 3600,
            "per_day": 86400,
        }

        # Exempt paths (no rate limiting)
        self.exempt_paths = [
            "/",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/api/v1/health",
        ]

        logger.info("RateLimitMiddleware initialized with tier-based limits")

    def get_user_tier_from_request(self, request: Request) -> str:
        """Extract user tier from request state.

        The auth middleware should have already populated request.state.user
        with the UserModel object.
        """
        if hasattr(request.state, "user") and request.state.user:
            return request.state.user.tier
        return UserTier.FREE.value  # Default to free tier for unauthenticated users

    def get_user_id_from_request(self, request: Request) -> str:
        """Extract user ID from request state or use IP address as fallback."""
        if hasattr(request.state, "user") and request.state.user:
            return request.state.user.user_id

        # Fallback to IP address for unauthenticated requests
        client_ip = request.client.host if request.client else "unknown"
        return f"ip:{client_ip}"

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with rate limiting."""

        # Skip rate limiting for exempt paths
        if request.url.path in self.exempt_paths:
            return await call_next(request)

        # Get user info
        user_id = self.get_user_id_from_request(request)
        user_tier = self.get_user_tier_from_request(request)

        # Get tier limits
        tier_limits = self.tier_limits.get(user_tier, self.tier_limits[UserTier.FREE.value])

        # Check rate limits for all windows
        for window_name, max_requests in tier_limits.items():
            window_seconds = self.windows[window_name]
            rate_limit_key = f"{user_id}:{window_name}"

            is_allowed, current_count, retry_after = await self.rate_limiter.check_rate_limit(
                key=rate_limit_key,
                max_requests=max_requests,
                window_seconds=window_seconds
            )

            if not is_allowed:
                logger.warning(
                    "rate_limit_rejected",
                    user_id=user_id,
                    tier=user_tier,
                    window=window_name,
                    current_count=current_count,
                    limit=max_requests,
                    path=request.url.path
                )

                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "error": "rate_limit_exceeded",
                        "message": f"Rate limit exceeded for {window_name}",
                        "details": {
                            "tier": user_tier,
                            "limit": max_requests,
                            "window": window_name,
                            "current": current_count,
                            "retry_after": retry_after
                        }
                    },
                    headers={
                        "Retry-After": str(retry_after),
                        "X-RateLimit-Limit": str(max_requests),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(int(time.time()) + retry_after)
                    }
                )

        # Process the request
        response = await call_next(request)

        # Add rate limit headers to response
        # Use the per_minute limit for headers (most commonly checked)
        per_minute_limit = tier_limits["per_minute"]
        per_minute_window = self.windows["per_minute"]
        per_minute_key = f"{user_id}:per_minute"

        current_usage = await self.rate_limiter.get_current_usage(
            per_minute_key,
            per_minute_window
        )

        remaining = max(0, per_minute_limit - current_usage)
        reset_time = int(time.time()) + per_minute_window

        response.headers["X-RateLimit-Limit"] = str(per_minute_limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_time)
        response.headers["X-RateLimit-Tier"] = user_tier

        return response


# Global rate limiter instance
rate_limiter = RateLimiter()
