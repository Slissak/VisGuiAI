"""Query timing middleware for profiling slow database queries.

This middleware tracks request timing and logs slow queries for performance analysis.
"""

import time
from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from ..utils.logging import get_logger

logger = get_logger(__name__)


class QueryTimingMiddleware(BaseHTTPMiddleware):
    """Middleware to track and log slow API requests and database queries.

    This middleware:
    - Tracks total request time
    - Logs requests that exceed the slow query threshold (default: 100ms)
    - Adds timing headers to responses for monitoring
    """

    def __init__(self, app, slow_query_threshold_ms: float = 100.0):
        """Initialize the query timing middleware.

        Args:
            app: The FastAPI application
            slow_query_threshold_ms: Threshold in milliseconds to log slow queries (default: 100ms)
        """
        super().__init__(app)
        self.slow_query_threshold_ms = slow_query_threshold_ms
        self.slow_query_threshold_seconds = slow_query_threshold_ms / 1000.0

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process the request and time it.

        Args:
            request: The incoming request
            call_next: The next middleware or route handler

        Returns:
            The response with timing headers added
        """
        # Record start time
        start_time = time.perf_counter()

        # Store start time in request state for access in route handlers
        request.state.request_start_time = start_time

        # Process the request
        response = await call_next(request)

        # Calculate total request time
        end_time = time.perf_counter()
        duration_seconds = end_time - start_time
        duration_ms = duration_seconds * 1000.0

        # Add timing headers to response
        response.headers["X-Request-Time-Ms"] = f"{duration_ms:.2f}"
        response.headers["X-Request-Time-Seconds"] = f"{duration_seconds:.4f}"

        # Log slow requests
        if duration_seconds > self.slow_query_threshold_seconds:
            logger.warning(
                "slow_request_detected",
                method=request.method,
                path=request.url.path,
                duration_ms=f"{duration_ms:.2f}",
                duration_seconds=f"{duration_seconds:.4f}",
                threshold_ms=self.slow_query_threshold_ms,
                status_code=response.status_code,
            )
        else:
            # Log normal requests at debug level
            logger.debug(
                "request_completed",
                method=request.method,
                path=request.url.path,
                duration_ms=f"{duration_ms:.2f}",
                status_code=response.status_code,
            )

        return response


class DatabaseQueryTimer:
    """Context manager for timing individual database queries.

    Usage:
        async with DatabaseQueryTimer("get_guide"):
            result = await db.execute(query)
    """

    def __init__(self, query_name: str, slow_threshold_ms: float = 100.0):
        """Initialize the database query timer.

        Args:
            query_name: Name/description of the query for logging
            slow_threshold_ms: Threshold in milliseconds to log slow queries (default: 100ms)
        """
        self.query_name = query_name
        self.slow_threshold_ms = slow_threshold_ms
        self.slow_threshold_seconds = slow_threshold_ms / 1000.0
        self.start_time = None
        self.duration_seconds = None

    async def __aenter__(self):
        """Enter the context manager and start timing."""
        self.start_time = time.perf_counter()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the context manager and log timing."""
        end_time = time.perf_counter()
        self.duration_seconds = end_time - self.start_time
        duration_ms = self.duration_seconds * 1000.0

        # Log slow queries
        if self.duration_seconds > self.slow_threshold_seconds:
            logger.warning(
                "slow_query_detected",
                query_name=self.query_name,
                duration_ms=f"{duration_ms:.2f}",
                duration_seconds=f"{self.duration_seconds:.4f}",
                threshold_ms=self.slow_threshold_ms,
            )
        else:
            # Log normal queries at debug level
            logger.debug(
                "query_completed",
                query_name=self.query_name,
                duration_ms=f"{duration_ms:.2f}",
            )

        return False  # Don't suppress exceptions


def get_request_duration_ms(request: Request) -> float:
    """Get the current request duration in milliseconds.

    Args:
        request: The current request

    Returns:
        Duration in milliseconds, or 0.0 if timing not available
    """
    if hasattr(request.state, "request_start_time"):
        start_time = request.state.request_start_time
        current_time = time.perf_counter()
        duration_seconds = current_time - start_time
        return duration_seconds * 1000.0
    return 0.0
