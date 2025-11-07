"""Database connection and session management."""

from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool, QueuePool

from ..utils.logging import get_logger
from .config import get_settings


class DatabaseManager:
    """Manages database connections and sessions."""

    def __init__(self):
        """Initialize database manager."""
        self.settings = get_settings()
        self.engine = None
        self.session_maker = None
        self.logger = get_logger(__name__)

    def initialize(self) -> None:
        """Initialize database engine and session maker."""
        database_url = self.settings.database_url

        # Configure engine based on environment
        engine_kwargs = {
            "echo": self.settings.debug,
            "future": True,
        }

        # Use NullPool for testing to avoid connection issues
        if self.settings.environment == "test":
            engine_kwargs["poolclass"] = NullPool
            self.logger.info(
                "database_pool_config", pool_type="NullPool", environment="test"
            )
        else:
            # Production connection pool settings
            engine_kwargs.update(
                {
                    "poolclass": QueuePool,
                    "pool_size": 20,  # Number of connections to maintain in the pool
                    "max_overflow": 10,  # Additional connections allowed beyond pool_size
                    "pool_pre_ping": True,  # Validate connections before using them
                    "pool_recycle": 3600,  # Recycle connections after 1 hour (3600 seconds)
                    "pool_timeout": 30,  # Timeout for getting a connection from the pool
                    "echo_pool": self.settings.debug,  # Log pool checkouts/checkins in debug mode
                }
            )
            self.logger.info(
                "database_pool_config",
                pool_type="QueuePool",
                pool_size=20,
                max_overflow=10,
                pool_pre_ping=True,
                pool_recycle=3600,
                pool_timeout=30,
                environment=self.settings.environment,
            )

        self.engine = create_async_engine(database_url, **engine_kwargs)
        self.session_maker = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        self.logger.info(
            "database_initialized",
            message="Database engine and session maker initialized",
        )

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get database session."""
        if not self.session_maker:
            raise RuntimeError("Database not initialized. Call initialize() first.")

        # Log warning if pool is under pressure (non-test environment)
        if self.settings.environment != "test" and self.engine:
            try:
                pool = self.engine.pool
                if not isinstance(pool, NullPool):
                    checked_out = pool.checkedout()
                    pool_size = pool.size()
                    overflow = pool.overflow()
                    max_overflow = getattr(pool, "_max_overflow", 10)

                    # Warn if pool is exhausted
                    if overflow >= max_overflow:
                        self.logger.warning(
                            "database_pool_exhausted",
                            checked_out=checked_out,
                            pool_size=pool_size,
                            overflow=overflow,
                            max_overflow=max_overflow,
                            message="Connection pool is exhausted. Consider increasing pool size or max_overflow.",
                        )
                    # Warn if pool is near capacity (80% of max connections)
                    elif checked_out > ((pool_size + max_overflow) * 0.8):
                        self.logger.warning(
                            "database_pool_near_capacity",
                            checked_out=checked_out,
                            pool_size=pool_size,
                            overflow=overflow,
                            capacity_percentage=round(
                                (checked_out / (pool_size + max_overflow)) * 100, 2
                            ),
                            message="Connection pool is near capacity.",
                        )
            except Exception as e:
                # Don't fail session creation if pool monitoring fails
                self.logger.debug(
                    "pool_monitoring_error",
                    error=str(e),
                    message="Failed to check pool status, continuing with session creation",
                )

        async with self.session_maker() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    async def close(self) -> None:
        """Close database connections."""
        if self.engine:
            await self.engine.dispose()

    def get_pool_status(self) -> dict[str, Any]:
        """Get current connection pool status and metrics.

        Returns:
            Dict containing pool statistics including size, checked out connections,
            overflow, and pool configuration.
        """
        if not self.engine:
            return {"status": "not_initialized"}

        pool = self.engine.pool

        # Check if this is a NullPool (testing environment)
        if isinstance(pool, NullPool):
            return {
                "status": "healthy",
                "pool_type": "NullPool",
                "environment": self.settings.environment,
                "note": "NullPool doesn't maintain persistent connections",
            }

        # For QueuePool, get detailed statistics
        try:
            return {
                "status": "healthy",
                "pool_type": "QueuePool",
                "size": pool.size(),  # Current number of connections in pool
                "checked_out": pool.checkedout(),  # Number of connections currently in use
                "overflow": pool.overflow(),  # Number of overflow connections
                "checked_in": pool.checkedin(),  # Number of connections available in pool
                "configuration": {
                    "pool_size": getattr(pool, "_pool_size", 20),
                    "max_overflow": getattr(pool, "_max_overflow", 10),
                    "timeout": getattr(pool, "_timeout", 30),
                    "recycle": getattr(pool, "_recycle", 3600),
                },
                "health": {
                    "pool_exhausted": pool.overflow()
                    >= getattr(pool, "_max_overflow", 10),
                    "near_capacity": pool.checkedout() > (pool.size() * 0.8),
                },
            }
        except Exception as e:
            self.logger.error(
                "pool_status_error", error=str(e), error_type=type(e).__name__
            )
            return {"status": "error", "error": str(e)}


# Global database manager instance
db_manager = DatabaseManager()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session."""
    async for session in db_manager.get_session():
        yield session


async def init_database() -> None:
    """Initialize database connection."""
    db_manager.initialize()


async def close_database() -> None:
    """Close database connection."""
    await db_manager.close()
