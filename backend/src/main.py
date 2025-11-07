"""FastAPI application for Step Guide Backend API.

This is the main entry point for the backend service.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .api.admin import router as admin_router
from .api.auth import router as auth_router

# Import API routers
from .api.guides import router as guides_router
from .api.instruction_guides import router as instruction_guides_router
from .api.progress import router as progress_router
from .api.sessions import router as sessions_router
from .api.steps import router as steps_router
from .auth.middleware import UserPopulationMiddleware
from .core.cache import cache_manager, close_cache, init_cache
from .core.config import get_settings
from .core.database import close_database, db_manager, get_db, init_database
from .core.redis import close_redis, init_redis, redis_manager
from .exceptions import GuideException
from .middleware import QueryTimingMiddleware, RateLimitMiddleware
from .services.llm_service import init_llm_service
from .utils.logging import get_logger, setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    settings = get_settings()

    # Initialize logging first
    setup_logging(settings.environment)
    logger = get_logger(__name__)

    # Startup
    try:
        logger.info(
            "starting_backend", environment=settings.environment, debug=settings.debug
        )
        await init_database()
        await init_redis()
        await init_cache()  # Initialize cache for enhanced Redis caching
        await init_llm_service()
        logger.info(
            "backend_started",
            environment=settings.environment,
            message="Step Guide Backend started successfully",
        )
    except Exception as e:
        logger.error("startup_failed", error=str(e), error_type=type(e).__name__)
        raise

    yield

    # Shutdown
    try:
        logger.info("shutting_down_backend")
        await close_cache()  # Close cache connections
        await close_database()
        await close_redis()
        logger.info("backend_shutdown_complete")
    except Exception as e:
        logger.error("shutdown_failed", error=str(e), error_type=type(e).__name__)


# Create FastAPI application
app = FastAPI(
    title="Step Guide Management System API",
    description="REST API for generating and managing step-by-step guides with progress tracking",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Get settings
settings = get_settings()

# User population middleware (add first to populate user for rate limiting)
app.add_middleware(UserPopulationMiddleware)

# Rate limiting middleware (add after user population to enforce tier-based limits)
app.add_middleware(RateLimitMiddleware)

# Query timing middleware (add after rate limiter to capture total request time)
app.add_middleware(
    QueryTimingMiddleware,
    slow_query_threshold_ms=100.0,  # Log queries taking more than 100ms
)

# GZip compression middleware
# Compress responses over 1000 bytes with compression level 6 (balance between speed and size)
app.add_middleware(
    GZipMiddleware,
    minimum_size=1000,  # Only compress responses larger than 1KB
    compresslevel=6,  # Balanced compression (1=fast/less compression, 9=slow/more compression)
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug else ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(GuideException)
async def guide_exception_handler(
    request: Request, exc: GuideException
) -> JSONResponse:
    """Exception handler for custom GuideException and its subclasses.

    Returns structured error responses with error codes, messages, and details.
    """
    return JSONResponse(
        status_code=400,
        content={
            "error": exc.code,
            "message": exc.message,
            "details": exc.details,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler for unhandled exceptions."""
    logger = get_logger(__name__)
    logger.error(
        "unhandled_exception",
        error=str(exc),
        error_type=type(exc).__name__,
        path=request.url.path,
    )

    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "message": "An internal server error occurred",
            "details": {"type": type(exc).__name__} if settings.debug else {},
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "request_id": getattr(request.state, "request_id", None),
        },
    )


# Include API routers
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(guides_router)
app.include_router(sessions_router)
app.include_router(steps_router)
app.include_router(progress_router)
app.include_router(instruction_guides_router)


# Enhanced health check endpoint with connection pool metrics
@app.get("/api/v1/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """Enhanced health check endpoint with database connectivity and pool metrics."""
    logger = get_logger(__name__)
    overall_status = "healthy"
    database_status = "unknown"
    redis_status = "unknown"
    db_pool_info = {}
    redis_pool_info = {}

    # Check database connectivity and pool status
    try:
        # Test database connection
        await db.execute(text("SELECT 1"))
        database_status = "connected"

        # Get database pool status
        db_pool_info = db_manager.get_pool_status()

        logger.debug(
            "health_check_database", status=database_status, pool_info=db_pool_info
        )
    except Exception as e:
        database_status = "error"
        overall_status = "unhealthy"
        logger.error(
            "health_check_database_failed", error=str(e), error_type=type(e).__name__
        )
        if settings.debug:
            db_pool_info = {"error": str(e)}

    # Check Redis connectivity and pool status
    try:
        redis_health = await redis_manager.health_check()
        redis_status = redis_health.get("status", "unknown")
        redis_pool_info = redis_health

        if redis_status != "healthy":
            overall_status = "degraded"

        logger.debug(
            "health_check_redis", status=redis_status, pool_info=redis_pool_info
        )
    except Exception as e:
        redis_status = "error"
        overall_status = "degraded"
        logger.error(
            "health_check_redis_failed", error=str(e), error_type=type(e).__name__
        )
        if settings.debug:
            redis_pool_info = {"error": str(e)}

    # Check cache availability
    cache_status = "available" if cache_manager.is_available else "unavailable"

    response = {
        "status": overall_status,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "version": "1.0.0",
        "services": {
            "database": {"status": database_status, "pool": db_pool_info},
            "redis": {"status": redis_status, "pool": redis_pool_info},
            "cache": {"status": cache_status},
        },
    }

    # Return appropriate HTTP status code
    if overall_status == "unhealthy":
        return JSONResponse(status_code=503, content=response)
    elif overall_status == "degraded":
        return JSONResponse(status_code=200, content=response)
    else:
        return response


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Step Guide Management System API",
        "version": "1.0.0",
        "docs_url": "/docs",
    }
