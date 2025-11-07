"""Redis connection and session store management."""

import json
from typing import Any

from redis.asyncio import ConnectionPool, Redis

from ..utils.logging import get_logger
from .config import get_settings


class RedisManager:
    """Manages Redis connections and operations."""

    def __init__(self):
        """Initialize Redis manager."""
        self.settings = get_settings()
        self.redis_client: Redis | None = None
        self.connection_pool: ConnectionPool | None = None
        self.logger = get_logger(__name__)

    async def initialize(self) -> None:
        """Initialize Redis connection with connection pool."""
        # Create connection pool for optimal connection reuse
        self.connection_pool = ConnectionPool.from_url(
            self.settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            max_connections=50,  # Maximum number of connections in the pool
            retry_on_timeout=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            socket_keepalive=True,  # Enable TCP keepalive
            health_check_interval=30,  # Check connection health every 30 seconds
        )

        # Create Redis client using the connection pool
        self.redis_client = Redis(connection_pool=self.connection_pool)

        # Test connection
        try:
            await self.redis_client.ping()
            self.logger.info(
                "redis_initialized",
                max_connections=50,
                health_check_interval=30,
                message="Redis connection pool initialized successfully",
            )
        except Exception as e:
            self.logger.error(
                "redis_connection_failed", error=str(e), error_type=type(e).__name__
            )
            raise ConnectionError(f"Failed to connect to Redis: {e}") from e

    async def close(self) -> None:
        """Close Redis connection and connection pool."""
        if self.redis_client:
            await self.redis_client.close()
        if self.connection_pool:
            await self.connection_pool.disconnect()
            self.logger.info(
                "redis_connection_pool_closed",
                message="Redis connection pool closed successfully",
            )

    def get_pool_status(self) -> dict[str, Any]:
        """Get current Redis connection pool status and metrics.

        Returns:
            Dict containing pool statistics including max connections,
            current connections, and pool health.
        """
        if not self.connection_pool:
            return {"status": "not_initialized"}

        try:
            # Get connection pool statistics
            pool = self.connection_pool
            max_connections = pool.max_connections

            # Note: redis-py doesn't expose all pool metrics directly,
            # but we can provide configuration info
            return {
                "status": "healthy",
                "configuration": {
                    "max_connections": max_connections,
                    "health_check_interval": 30,
                    "socket_keepalive": True,
                    "retry_on_timeout": True,
                },
                "note": "Redis connection pool is active and healthy",
            }
        except Exception as e:
            self.logger.error(
                "redis_pool_status_error", error=str(e), error_type=type(e).__name__
            )
            return {"status": "error", "error": str(e)}

    async def health_check(self) -> dict[str, Any]:
        """Perform comprehensive Redis health check.

        Returns:
            Dict containing health status, connectivity, and performance metrics.
        """
        if not self.redis_client:
            return {"status": "unhealthy", "error": "Redis client not initialized"}

        try:
            # Test basic connectivity with ping
            import time

            start_time = time.time()
            await self.redis_client.ping()
            ping_latency_ms = round((time.time() - start_time) * 1000, 2)

            # Get Redis info
            info = await self.redis_client.info("stats")

            return {
                "status": "healthy",
                "ping_latency_ms": ping_latency_ms,
                "connected_clients": info.get("connected_clients", "unknown"),
                "total_connections_received": info.get(
                    "total_connections_received", "unknown"
                ),
                "pool": self.get_pool_status(),
            }
        except Exception as e:
            self.logger.error(
                "redis_health_check_failed", error=str(e), error_type=type(e).__name__
            )
            return {
                "status": "unhealthy",
                "error": str(e),
                "error_type": type(e).__name__,
            }

    async def get(self, key: str) -> str | None:
        """Get value by key."""
        if not self.redis_client:
            raise RuntimeError("Redis not initialized")
        return await self.redis_client.get(key)

    async def set(
        self, key: str, value: str, ex: int | None = None, nx: bool = False
    ) -> bool:
        """Set key-value with optional expiration."""
        if not self.redis_client:
            raise RuntimeError("Redis not initialized")
        return await self.redis_client.set(key, value, ex=ex, nx=nx)

    async def delete(self, key: str) -> int:
        """Delete key."""
        if not self.redis_client:
            raise RuntimeError("Redis not initialized")
        return await self.redis_client.delete(key)

    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        if not self.redis_client:
            raise RuntimeError("Redis not initialized")
        return bool(await self.redis_client.exists(key))

    async def expire(self, key: str, seconds: int) -> bool:
        """Set expiration for key."""
        if not self.redis_client:
            raise RuntimeError("Redis not initialized")
        return await self.redis_client.expire(key, seconds)


class SessionStore:
    """Session store using Redis for caching session data."""

    def __init__(self, redis_manager: RedisManager):
        """Initialize session store."""
        self.redis = redis_manager
        self.session_ttl = 30 * 24 * 60 * 60  # 30 days in seconds

    async def store_session(
        self, session_id: str, session_data: dict[str, Any]
    ) -> None:
        """Store session data."""
        key = f"session:{session_id}"
        value = json.dumps(session_data, default=str)
        await self.redis.set(key, value, ex=self.session_ttl)

    async def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Get session data."""
        key = f"session:{session_id}"
        value = await self.redis.get(key)
        if value:
            return json.loads(value)
        return None

    async def update_session(self, session_id: str, updates: dict[str, Any]) -> None:
        """Update session data."""
        existing = await self.get_session(session_id)
        if existing:
            existing.update(updates)
            await self.store_session(session_id, existing)

    async def delete_session(self, session_id: str) -> None:
        """Delete session data."""
        key = f"session:{session_id}"
        await self.redis.delete(key)

    async def store_user_sessions(self, user_id: str, session_ids: list) -> None:
        """Store user's active session IDs."""
        key = f"user_sessions:{user_id}"
        value = json.dumps(session_ids)
        await self.redis.set(key, value, ex=self.session_ttl)

    async def get_user_sessions(self, user_id: str) -> list:
        """Get user's active session IDs."""
        key = f"user_sessions:{user_id}"
        value = await self.redis.get(key)
        if value:
            return json.loads(value)
        return []

    async def add_user_session(self, user_id: str, session_id: str) -> None:
        """Add session to user's active sessions."""
        sessions = await self.get_user_sessions(user_id)
        if session_id not in sessions:
            sessions.append(session_id)
            await self.store_user_sessions(user_id, sessions)

    async def remove_user_session(self, user_id: str, session_id: str) -> None:
        """Remove session from user's active sessions."""
        sessions = await self.get_user_sessions(user_id)
        if session_id in sessions:
            sessions.remove(session_id)
            await self.store_user_sessions(user_id, sessions)

    async def store_progress(
        self, session_id: str, progress_data: dict[str, Any]
    ) -> None:
        """Store real-time progress updates."""
        key = f"step_progress:{session_id}"
        value = json.dumps(progress_data, default=str)
        # Shorter TTL for progress updates
        await self.redis.set(key, value, ex=7 * 24 * 60 * 60)  # 7 days

    async def get_progress(self, session_id: str) -> dict[str, Any] | None:
        """Get real-time progress data."""
        key = f"step_progress:{session_id}"
        value = await self.redis.get(key)
        if value:
            return json.loads(value)
        return None


# Global Redis manager instance
redis_manager = RedisManager()


async def get_redis() -> RedisManager:
    """Dependency to get Redis manager."""
    return redis_manager


async def get_session_store() -> SessionStore:
    """Dependency to get session store."""
    return SessionStore(redis_manager)


async def init_redis() -> None:
    """Initialize Redis connection."""
    await redis_manager.initialize()


async def close_redis() -> None:
    """Close Redis connection."""
    await redis_manager.close()
