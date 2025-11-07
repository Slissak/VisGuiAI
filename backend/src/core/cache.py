"""Enhanced Redis cache wrapper with graceful degradation."""

import hashlib
import json
from collections.abc import Callable
from functools import wraps
from typing import Any

import redis.asyncio as redis
from redis.asyncio import Redis

from ..utils.logging import get_logger
from .config import get_settings

logger = get_logger(__name__)


class CacheManager:
    """
    Enhanced Redis cache manager with graceful degradation.

    Features:
    - Automatic fallback when Redis is unavailable
    - TTL support for different data types
    - JSON serialization/deserialization
    - Cache key namespacing
    - Connection pooling
    """

    # Default TTL values (in seconds)
    TTL_GUIDE_DATA = 60 * 60  # 1 hour
    TTL_SESSION_STATE = 30 * 60  # 30 minutes
    TTL_LLM_RESPONSE = 24 * 60 * 60  # 24 hours
    TTL_STEP_PROGRESS = 7 * 24 * 60 * 60  # 7 days

    def __init__(self):
        """Initialize cache manager."""
        self.settings = get_settings()
        self.redis_client: Redis | None = None
        self.is_available = False
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize Redis connection with graceful degradation."""
        if self._initialized:
            return

        try:
            self.redis_client = redis.from_url(
                self.settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
                retry_on_timeout=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                max_connections=10,  # Connection pool size
            )

            # Test connection
            await self.redis_client.ping()
            self.is_available = True
            logger.info("cache_initialized", redis_url=self.settings.redis_url)

        except Exception as e:
            self.is_available = False
            logger.warning(
                "cache_unavailable",
                error=str(e),
                message="Cache will operate in fallback mode (no caching)",
            )

        self._initialized = True

    async def close(self) -> None:
        """Close Redis connection."""
        if self.redis_client:
            await self.redis_client.close()
            self.redis_client = None
            self.is_available = False
            self._initialized = False
            logger.info("cache_closed")

    async def get(self, key: str) -> Any | None:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found or cache unavailable
        """
        if not self.is_available or not self.redis_client:
            return None

        try:
            value = await self.redis_client.get(key)
            if value:
                logger.debug("cache_hit", key=key)
                return json.loads(value)
            logger.debug("cache_miss", key=key)
            return None

        except Exception as e:
            logger.warning("cache_get_error", key=key, error=str(e))
            return None

    async def set(
        self, key: str, value: Any, ttl: int | None = None, nx: bool = False
    ) -> bool:
        """
        Set value in cache with optional TTL.

        Args:
            key: Cache key
            value: Value to cache (will be JSON serialized)
            ttl: Time-to-live in seconds
            nx: Only set if key doesn't exist

        Returns:
            True if successful, False otherwise
        """
        if not self.is_available or not self.redis_client:
            return False

        try:
            serialized_value = json.dumps(value, default=str)
            result = await self.redis_client.set(key, serialized_value, ex=ttl, nx=nx)

            if result:
                logger.debug("cache_set", key=key, ttl=ttl, nx=nx)

            return bool(result)

        except Exception as e:
            logger.warning("cache_set_error", key=key, error=str(e))
            return False

    async def delete(self, key: str) -> bool:
        """
        Delete key from cache.

        Args:
            key: Cache key

        Returns:
            True if key was deleted, False otherwise
        """
        if not self.is_available or not self.redis_client:
            return False

        try:
            result = await self.redis_client.delete(key)
            logger.debug("cache_delete", key=key, deleted=bool(result))
            return bool(result)

        except Exception as e:
            logger.warning("cache_delete_error", key=key, error=str(e))
            return False

    async def delete_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching a pattern.

        Args:
            pattern: Key pattern (e.g., "guide:*")

        Returns:
            Number of keys deleted
        """
        if not self.is_available or not self.redis_client:
            return 0

        try:
            # Scan for keys matching pattern
            keys_to_delete = []
            async for key in self.redis_client.scan_iter(match=pattern):
                keys_to_delete.append(key)

            if keys_to_delete:
                deleted = await self.redis_client.delete(*keys_to_delete)
                logger.info("cache_pattern_delete", pattern=pattern, deleted=deleted)
                return deleted

            return 0

        except Exception as e:
            logger.warning("cache_pattern_delete_error", pattern=pattern, error=str(e))
            return 0

    async def exists(self, key: str) -> bool:
        """
        Check if key exists in cache.

        Args:
            key: Cache key

        Returns:
            True if key exists, False otherwise
        """
        if not self.is_available or not self.redis_client:
            return False

        try:
            result = await self.redis_client.exists(key)
            return bool(result)

        except Exception as e:
            logger.warning("cache_exists_error", key=key, error=str(e))
            return False

    async def expire(self, key: str, seconds: int) -> bool:
        """
        Set expiration for key.

        Args:
            key: Cache key
            seconds: TTL in seconds

        Returns:
            True if successful, False otherwise
        """
        if not self.is_available or not self.redis_client:
            return False

        try:
            result = await self.redis_client.expire(key, seconds)
            logger.debug("cache_expire", key=key, seconds=seconds)
            return bool(result)

        except Exception as e:
            logger.warning("cache_expire_error", key=key, error=str(e))
            return False

    # Namespaced cache key helpers

    @staticmethod
    def make_guide_key(guide_id: str) -> str:
        """Create cache key for guide data."""
        return f"guide:{guide_id}"

    @staticmethod
    def make_session_key(session_id: str) -> str:
        """Create cache key for session data."""
        return f"session:{session_id}"

    @staticmethod
    def make_llm_key(prompt: str, difficulty: str) -> str:
        """Create cache key for LLM response."""
        # Hash the prompt to create a consistent key
        prompt_hash = hashlib.sha256(f"{prompt}:{difficulty}".encode()).hexdigest()[:16]
        return f"llm:{prompt_hash}"

    @staticmethod
    def make_progress_key(session_id: str) -> str:
        """Create cache key for step progress."""
        return f"progress:{session_id}"

    @staticmethod
    def make_user_sessions_key(user_id: str) -> str:
        """Create cache key for user sessions list."""
        return f"user_sessions:{user_id}"


# Decorator for caching function results
def cached(ttl: int, key_prefix: str, key_builder: Callable | None = None):
    """
    Decorator for caching function results.

    Args:
        ttl: Time-to-live in seconds
        key_prefix: Prefix for cache key
        key_builder: Optional function to build cache key from args

    Example:
        @cached(ttl=3600, key_prefix="guide", key_builder=lambda guide_id: guide_id)
        async def get_guide(guide_id: str):
            # ... expensive operation ...
            return guide_data
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get cache manager from global instance
            cache = cache_manager

            # Build cache key
            if key_builder:
                key_suffix = key_builder(*args, **kwargs)
            else:
                # Default: use first argument as key suffix
                key_suffix = str(args[0]) if args else "default"

            cache_key = f"{key_prefix}:{key_suffix}"

            # Try to get from cache
            cached_value = await cache.get(cache_key)
            if cached_value is not None:
                return cached_value

            # Execute function
            result = await func(*args, **kwargs)

            # Cache the result
            if result is not None:
                await cache.set(cache_key, result, ttl=ttl)

            return result

        return wrapper

    return decorator


# Global cache manager instance
cache_manager = CacheManager()


async def get_cache() -> CacheManager:
    """Dependency to get cache manager."""
    return cache_manager


async def init_cache() -> None:
    """Initialize cache connection."""
    await cache_manager.initialize()


async def close_cache() -> None:
    """Close cache connection."""
    await cache_manager.close()
