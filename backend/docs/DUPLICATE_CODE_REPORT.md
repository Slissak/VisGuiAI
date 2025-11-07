# Duplicate Code Analysis Report

**Generated:** 2025-11-07
**Project:** VisGuiAI Backend
**Total Lines Analyzed:** ~7,943 (API, Services, Middleware)

---

## Executive Summary

- **Duplicate code blocks found:** 12 major patterns
- **Estimated lines duplicated:** ~850 lines
- **Refactoring opportunities:** 8 high-impact areas
- **Potential LOC reduction:** ~600-700 lines (75-82% reduction in duplicated code)
- **Code duplication rate:** ~10.7% across API/Services/Middleware

---

## 1. Exact Duplicates

### Duplicate Set #1: Session Ownership Verification Pattern

**Severity:** HIGH
**Occurrences:** 10 instances
**Estimated Duplicate Lines:** ~150 lines

**Locations:**
- `src/api/sessions.py`: Lines 96-108 (update_session)
- `src/api/sessions.py`: Lines 165-177 (advance_to_next_step)
- `src/api/steps.py`: Lines 97-109 (complete_step)
- `src/api/steps.py`: Lines 204-216 (mark_needs_assistance)
- `src/api/steps.py`: Lines 327-339 (get_session_steps)
- `src/api/progress.py`: ~4 similar occurrences

**Code Pattern:**
```python
# First verify user owns this session
session_detail = await session_service.get_session(session_id, db)
if not session_detail:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Session {session_id} not found"
    )

if session_detail.session.user_id != current_user:
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Access denied to this session"
    )
```

**Recommendation:**
Create a dependency or decorator in `src/api/dependencies.py`:

```python
async def verify_session_ownership(
    session_id: uuid.UUID,
    current_user: str,
    session_service: SessionService,
    db: AsyncSession
) -> SessionDetailResponse:
    """Verify user owns session and return session detail."""
    session_detail = await session_service.get_session(session_id, db)
    if not session_detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found"
        )

    if session_detail.session.user_id != current_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this session"
        )

    return session_detail

# Usage as dependency:
async def get_session_with_ownership(
    session_id: uuid.UUID,
    current_user: str = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_service),
    db: AsyncSession = Depends(get_db)
) -> SessionDetailResponse:
    return await verify_session_ownership(session_id, current_user, session_service, db)
```

**Impact:** Reduces 150 lines to ~40 lines, improves consistency and security

---

### Duplicate Set #2: Database Commit Pattern

**Severity:** MEDIUM
**Occurrences:** 10+ files
**Estimated Duplicate Lines:** ~30 lines (scattered)

**Locations:**
- `src/api/admin.py`: Lines 296-297, 351
- `src/api/auth.py`: Lines 258-259, 466
- `src/auth/middleware.py`: Lines 91-92, 199-200
- `src/services/guide_service.py`: Lines 88, 156, 327, 358
- `src/services/session_service.py`: Lines 88, 156, 278, 371
- `src/services/step_service.py`: Line 106

**Code Pattern:**
```python
await db.commit()
await db.refresh(user)  # or session, guide, etc.
```

**Recommendation:**
While this pattern is simple, it's repeated frequently. Consider creating a utility function in `src/utils/database_helpers.py`:

```python
from typing import TypeVar
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from ..utils.logging import get_logger

T = TypeVar('T')
logger = get_logger(__name__)

async def commit_and_refresh(
    db: AsyncSession,
    obj: T,
    operation: str = "database_operation"
) -> T:
    """Commit transaction and refresh object with error handling.

    Args:
        db: Database session
        obj: SQLAlchemy model instance to refresh
        operation: Operation name for logging

    Returns:
        Refreshed object

    Raises:
        HTTPException: 500 on database errors
    """
    try:
        await db.commit()
        await db.refresh(obj)
        return obj
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error(f"{operation}_database_error", error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Database error occurred"
        )
```

**Impact:** MEDIUM - Adds error handling consistency, reduces ~10 lines across files

---

### Duplicate Set #3: Redis Availability Check Pattern

**Severity:** MEDIUM
**Occurrences:** 10 instances in abuse_detection.py, 2 in rate_limiter.py
**Estimated Duplicate Lines:** ~120 lines

**Locations:**
- `src/services/abuse_detection.py`: Lines 184-194, 196-207, 209-220, 255-281, 283-308, 310-322, 324-335, 337-348
- `src/middleware/rate_limiter.py`: Lines 51-54, 130-131

**Code Pattern:**
```python
if not redis_manager.is_available:
    return 0  # or return [] or return

try:
    # Redis operations
    key = f"some_key:{user_id}"
    result = await redis_manager.client.operation(key)
    return result
except Exception as e:
    logger.error("operation_redis_error", error=str(e), metric="metric_name")
    return 0  # or default value
```

**Recommendation:**
Create a decorator or context manager in `src/core/redis.py`:

```python
from functools import wraps
from typing import Any, Callable, TypeVar, Optional

T = TypeVar('T')

def with_redis_fallback(
    default_value: Any,
    metric_name: str,
    log_errors: bool = True
):
    """Decorator for Redis operations with fallback on failure.

    Args:
        default_value: Value to return if Redis is unavailable or fails
        metric_name: Name of metric for logging
        log_errors: Whether to log errors
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(self, *args, **kwargs) -> T:
            if not self.redis_manager.is_available:
                if log_errors:
                    self.logger.warning(
                        f"{metric_name}_redis_unavailable",
                        message="Redis unavailable, using fallback"
                    )
                return default_value

            try:
                return await func(self, *args, **kwargs)
            except Exception as e:
                if log_errors:
                    self.logger.error(
                        f"{metric_name}_redis_error",
                        error=str(e),
                        error_type=type(e).__name__
                    )
                return default_value
        return wrapper
    return decorator

# Usage:
@with_redis_fallback(default_value=0, metric_name="requests_per_hour")
async def _get_requests_per_hour(self, user_id: str) -> int:
    """Get request count from Redis rate limiter."""
    key = f"rate_limit:user:{user_id}:per_minute"
    count = await self.redis_manager.client.zcard(key)
    return count * 60
```

**Impact:** Reduces ~120 lines to ~40 lines, improves maintainability

---

### Duplicate Set #4: User Authorization Check (Admin Endpoints)

**Severity:** LOW-MEDIUM
**Occurrences:** 8 instances
**Estimated Duplicate Lines:** ~80 lines

**Locations:**
- `src/api/sessions.py`: Lines 37-41, 140-144
- Similar patterns in other API files for user ID verification

**Code Pattern:**
```python
# Ensure the user_id in request matches authenticated user
if request.user_id != current_user:
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Cannot create session for another user"
    )
```

**Recommendation:**
Create validator function in `src/api/dependencies.py`:

```python
def verify_user_match(request_user_id: str, current_user: str) -> None:
    """Verify request user_id matches authenticated user.

    Args:
        request_user_id: User ID from request
        current_user: Authenticated user ID

    Raises:
        HTTPException: 403 if user IDs don't match
    """
    if request_user_id != current_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot perform operation for another user"
        )
```

**Impact:** Reduces ~80 lines to ~20 lines

---

## 2. Similar Patterns (Refactorable)

### Pattern #1: HTTPException Boilerplate

**Severity:** HIGH
**Occurrences:** 95+ instances across 10 files
**Estimated Duplicate Lines:** ~285 lines

**Found in:**
- All API route files (guides.py, sessions.py, steps.py, admin.py, etc.)

**Pattern:**
```python
try:
    # Operation
    response = await service.operation(request, db)
    return response
except ValueError as e:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=str(e)
    )
except Exception as e:
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Failed to operation: {str(e)}"
    )
```

**Recommendation:**
Create exception handler decorator in `src/api/error_handlers.py`:

```python
from functools import wraps
from typing import Callable, TypeVar
from fastapi import HTTPException, status

T = TypeVar('T')

def handle_api_errors(operation_name: str = "operation"):
    """Decorator to handle common API exceptions.

    Args:
        operation_name: Name of operation for error messages
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            try:
                return await func(*args, **kwargs)
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(e)
                )
            except SessionNotFoundError as e:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=str(e)
                )
            except InvalidSessionStateError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(e)
                )
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to {operation_name}: {str(e)}"
                )
        return wrapper
    return decorator

# Usage:
@router.post("/sessions")
@handle_api_errors(operation_name="create session")
async def create_session(
    request: SessionCreateRequest,
    current_user: str = Depends(get_current_user),
    # ... other dependencies
):
    """Create a new guide session."""
    # Operation logic only, no try/except needed
    verify_user_match(request.user_id, current_user)
    guide_service = GuideService(llm_service)
    session_service = SessionService(guide_service, session_store)
    return await session_service.create_session(request, db)
```

**Impact:** Reduces ~285 lines to ~60 lines, centralizes error handling

---

### Pattern #2: Pagination Logic

**Severity:** MEDIUM
**Occurrences:** 2 instances
**Estimated Duplicate Lines:** ~30 lines

**Locations:**
- `src/api/admin.py`: Lines 169-186 (list_users)
- `src/api/admin.py`: Lines 449-455 (get_usage_stats)

**Pattern:**
```python
# Get total count
count_query = select(func.count()).select_from(query.subquery())
result = await db.execute(count_query)
total = result.scalar()

# Apply pagination
offset = (page - 1) * page_size
query = query.offset(offset).limit(page_size)
```

**Recommendation:**
Create pagination utility in `src/utils/pagination.py`:

```python
from typing import TypeVar, Generic, List
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar('T')

class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response."""
    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int

async def paginate(
    db: AsyncSession,
    query: select,
    page: int,
    page_size: int
) -> tuple[List, int]:
    """Apply pagination to SQLAlchemy query.

    Args:
        db: Database session
        query: SQLAlchemy select query
        page: Page number (1-indexed)
        page_size: Items per page

    Returns:
        Tuple of (items, total_count)
    """
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    result = await db.execute(count_query)
    total = result.scalar()

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    # Execute query
    result = await db.execute(query)
    items = result.scalars().all()

    return items, total
```

**Impact:** Reduces ~30 lines to ~10 lines

---

### Pattern #3: Development User Creation (Auth Middleware)

**Severity:** LOW
**Occurrences:** 2 instances (exact duplicates)
**Estimated Duplicate Lines:** ~40 lines

**Locations:**
- `src/auth/middleware.py`: Lines 72-92 (get_current_user)
- `src/auth/middleware.py`: Lines 181-200 (UserPopulationMiddleware.dispatch)

**Code Pattern:**
```python
if settings.environment == "development" and user_id == "dev-user-id":
    # Check if dev user exists
    result = await db.execute(
        select(UserModel).where(UserModel.user_id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        # Create dev user with free tier
        user = UserModel(
            user_id=user_id,
            email="dev@example.com",
            hashed_password="dev_password_hash",
            tier="free",
            full_name="Dev User",
            is_active=True,
            is_verified=True
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    return user
```

**Recommendation:**
Extract to helper function in `src/auth/middleware.py`:

```python
async def get_or_create_dev_user(
    db: AsyncSession,
    user_id: str = "dev-user-id"
) -> UserModel:
    """Get or create development user.

    Args:
        db: Database session
        user_id: Development user ID

    Returns:
        Development user model
    """
    result = await db.execute(
        select(UserModel).where(UserModel.user_id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        user = UserModel(
            user_id=user_id,
            email="dev@example.com",
            hashed_password="dev_password_hash",
            tier="free",
            full_name="Dev User",
            is_active=True,
            is_verified=True
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    return user
```

**Impact:** Reduces ~40 lines to ~5 lines (2 call sites)

---

### Pattern #4: SQLAlchemy Eager Loading with selectinload

**Severity:** LOW
**Occurrences:** 10+ instances
**Estimated Duplicate Lines:** ~40 lines (pattern recognition)

**Locations:**
- `src/services/session_service.py`: Lines 118-120, 232-234, 249-251, 307-309, 375-377
- `src/services/guide_service.py`: Lines 137-140

**Pattern:**
```python
query = select(GuideSessionModel).options(
    selectinload(GuideSessionModel.guide),
    selectinload(GuideSessionModel.progress_tracker)
).where(GuideSessionModel.session_id == session_id)
result = await db.execute(query)
session_model = result.scalar_one_or_none()
```

**Recommendation:**
Create query builder utilities in `src/utils/query_builders.py`:

```python
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from ..models.database import GuideSessionModel, StepGuideModel

def get_session_with_relations():
    """Get session query with standard relationship eager loading."""
    return select(GuideSessionModel).options(
        selectinload(GuideSessionModel.guide),
        selectinload(GuideSessionModel.progress_tracker)
    )

def get_guide_with_steps():
    """Get guide query with steps eager loaded."""
    return select(StepGuideModel).options(
        selectinload(StepGuideModel.steps),
        selectinload(StepGuideModel.sections)
    )
```

**Impact:** MEDIUM - Improves query consistency and reduces N+1 query risks

---

## 3. Repeated Validation Logic

### Validation #1: Password Strength Validation

**Severity:** LOW
**Occurrences:** 1 instance (could be reused in password change endpoints)
**Estimated Duplicate Lines:** N/A (single use currently)

**Location:**
- `src/api/auth.py`: Lines 49-77

**Recommendation:**
Move to `src/utils/validation.py` for reuse in future password change/reset features:

```python
import re
from typing import List

class PasswordValidationError(ValueError):
    """Exception raised when password validation fails."""
    pass

def validate_password_strength(password: str) -> None:
    """Validate password meets strength requirements.

    Requirements:
        - Minimum 8 characters
        - At least 1 uppercase letter
        - At least 1 lowercase letter
        - At least 1 number

    Args:
        password: Password to validate

    Raises:
        PasswordValidationError: If password doesn't meet requirements
    """
    errors: List[str] = []

    if len(password) < 8:
        errors.append('Password must be at least 8 characters long')
    if not re.search(r'[A-Z]', password):
        errors.append('Password must contain at least one uppercase letter')
    if not re.search(r'[a-z]', password):
        errors.append('Password must contain at least one lowercase letter')
    if not re.search(r'\d', password):
        errors.append('Password must contain at least one number')

    if errors:
        raise PasswordValidationError('; '.join(errors))
```

**Impact:** LOW - Enables reuse for future password change features

---

## 4. Refactoring Priorities

### High Priority (Most Impact)

#### 1. Session Ownership Verification (Priority: CRITICAL)
- **Files affected:** 5+ API endpoint files
- **Duplicate lines:** ~150
- **Estimated reduction:** ~110 lines (73%)
- **Risk level:** LOW (well-tested pattern)
- **Security benefit:** HIGH (centralizes security-critical logic)
- **Effort:** 2-3 hours

#### 2. HTTPException Error Handling (Priority: HIGH)
- **Files affected:** 10 files
- **Duplicate lines:** ~285
- **Estimated reduction:** ~225 lines (79%)
- **Risk level:** MEDIUM (need comprehensive testing)
- **Effort:** 4-5 hours

#### 3. Redis Availability Check Pattern (Priority: HIGH)
- **Files affected:** 2 files (abuse_detection.py, rate_limiter.py)
- **Duplicate lines:** ~120
- **Estimated reduction:** ~80 lines (67%)
- **Risk level:** LOW (fail-safe pattern)
- **Effort:** 2-3 hours

### Medium Priority

#### 4. Database Commit Pattern (Priority: MEDIUM)
- **Files affected:** 10+ files
- **Duplicate lines:** ~30
- **Estimated reduction:** ~10 lines (33%)
- **Risk level:** LOW
- **Benefit:** Adds consistent error handling
- **Effort:** 1-2 hours

#### 5. User Authorization Check (Priority: MEDIUM)
- **Files affected:** 4 files
- **Duplicate lines:** ~80
- **Estimated reduction:** ~60 lines (75%)
- **Risk level:** LOW
- **Effort:** 1-2 hours

#### 6. Pagination Logic (Priority: MEDIUM)
- **Files affected:** 1 file (admin.py), potentially more
- **Duplicate lines:** ~30
- **Estimated reduction:** ~20 lines (67%)
- **Risk level:** LOW
- **Effort:** 1 hour

### Low Priority

#### 7. Development User Creation (Priority: LOW)
- **Files affected:** 1 file
- **Duplicate lines:** ~40
- **Estimated reduction:** ~35 lines (88%)
- **Risk level:** VERY LOW (dev-only code)
- **Effort:** 30 minutes

#### 8. SQLAlchemy Query Builders (Priority: LOW)
- **Files affected:** 3-4 files
- **Duplicate lines:** ~40
- **Estimated reduction:** ~20 lines (50%)
- **Risk level:** LOW
- **Benefit:** Improved query consistency
- **Effort:** 1-2 hours

---

## 5. Proposed Refactoring Plan

### Phase 1: Create Utility Infrastructure (4-6 hours)

**New Files to Create:**
1. `src/api/dependencies.py` - Shared API dependencies
2. `src/api/error_handlers.py` - Centralized error handling
3. `src/utils/database_helpers.py` - Database operation utilities
4. `src/utils/pagination.py` - Pagination utilities
5. `src/utils/redis_helpers.py` - Redis operation decorators

**Tasks:**
- [ ] Create `verify_session_ownership()` dependency
- [ ] Create `verify_user_match()` validator
- [ ] Create `handle_api_errors()` decorator
- [ ] Create `commit_and_refresh()` utility
- [ ] Create `with_redis_fallback()` decorator
- [ ] Create `paginate()` utility
- [ ] Add comprehensive unit tests for all utilities

### Phase 2: Refactor High Priority Items (6-8 hours)

**Order of Refactoring:**
1. Session ownership verification (highest security impact)
2. Redis availability check pattern (most duplicate lines)
3. HTTPException error handling (largest scope)

**Approach:**
- Refactor one file at a time
- Run test suite after each file
- Use feature flags if necessary for gradual rollout

**Tasks:**
- [ ] Refactor `src/api/sessions.py` to use new dependencies
- [ ] Refactor `src/api/steps.py` to use new dependencies
- [ ] Refactor `src/api/progress.py` to use new dependencies
- [ ] Refactor `src/services/abuse_detection.py` to use Redis decorator
- [ ] Refactor `src/middleware/rate_limiter.py` to use Redis decorator
- [ ] Apply error handler decorator to all API endpoints
- [ ] Run full integration test suite

### Phase 3: Refactor Medium Priority Items (4-5 hours)

**Tasks:**
- [ ] Replace database commit patterns with `commit_and_refresh()`
- [ ] Replace user authorization checks with `verify_user_match()`
- [ ] Replace pagination logic with `paginate()` utility
- [ ] Run test suite after each change

### Phase 4: Test & Validate (2-3 hours)

**Tasks:**
- [ ] Run full test suite (unit, integration, contract)
- [ ] Manual API testing with Postman/curl
- [ ] Performance regression testing
- [ ] Code review with focus on security implications
- [ ] Update documentation

---

## 6. Risk Assessment

### Low Risk (Safe to Refactor Immediately)

✅ **Session ownership verification**
- Well-defined pattern
- Critical security logic that should be centralized
- Easy to test

✅ **Database commit pattern**
- Simple utility function
- Adds error handling (net improvement)
- Low coupling

✅ **Pagination logic**
- Self-contained utility
- Easy to test

### Medium Risk (Need Comprehensive Testing)

⚠️ **HTTPException error handling**
- Affects all API endpoints
- Need to ensure all exception types are handled
- Requires comprehensive integration testing
- Could affect client error handling

⚠️ **Redis availability check pattern**
- Different contexts might need different fallback behavior
- Need to verify fail-safe behavior in each case
- Test with Redis unavailable scenarios

### High Risk (Investigate & Plan Carefully)

🔴 **None identified** - All patterns are safe to refactor with proper testing

---

## 7. Code Quality Metrics

### Current State

**Duplication Metrics:**
- Total lines in API/Services/Middleware: ~7,943
- Estimated duplicate lines: ~850
- Code duplication rate: **~10.7%**
- HTTPException boilerplate: 95+ instances
- Database commit operations: 10+ files
- Session ownership checks: 10 instances

**Complexity Indicators:**
- Average function length: ~25 lines (acceptable)
- Files with duplicates: 15/30 (~50%)
- Security-critical duplicates: 10 instances (session verification)

### After Refactoring (Projected)

**Duplication Metrics:**
- Expected duplicate lines: ~150-200
- Expected duplication rate: **~2-3%**
- HTTPException boilerplate: 1 decorator
- Database operations: 1 utility function
- Session ownership checks: 1 dependency

**Improvements:**
- Code duplication reduction: **75-80%**
- LOC reduction: **~600-700 lines**
- Security: Centralized auth checks
- Maintainability: Easier to update error handling, validation
- Testing: Easier to test utilities in isolation
- Consistency: All endpoints use same error handling

---

## 8. Additional Observations

### Positive Patterns (Don't Change)

✅ **Consistent use of async/await**
- All database operations are properly async
- Good use of AsyncSession

✅ **Structured logging**
- Good use of structured logging with context
- Logger instances properly initialized

✅ **Type hints**
- Excellent type hint coverage
- Pydantic models for request/response validation

✅ **Dependency injection**
- Good use of FastAPI Depends
- Proper separation of concerns

### Areas for Future Improvement (Beyond Duplication)

💡 **Import organization**
- Some files have mixed import styles
- Could benefit from isort configuration

💡 **Error messages**
- Some error messages could be more user-friendly
- Consider separating user-facing vs. log messages

💡 **Docstrings**
- Good coverage in most files
- Some utility functions could use more examples

---

## 9. Estimated Timeline

### Conservative Estimate (with testing)
- **Phase 1 (Infrastructure):** 4-6 hours
- **Phase 2 (High Priority):** 6-8 hours
- **Phase 3 (Medium Priority):** 4-5 hours
- **Phase 4 (Testing & Validation):** 2-3 hours
- **Total:** 16-22 hours (2-3 days)

### Aggressive Estimate (minimal testing)
- **Phase 1:** 3-4 hours
- **Phase 2:** 4-5 hours
- **Phase 3:** 2-3 hours
- **Phase 4:** 1-2 hours
- **Total:** 10-14 hours (1.5-2 days)

**Recommended:** Conservative approach with comprehensive testing

---

## 10. Next Steps

### Immediate Actions

1. **Review & Approve Plan**
   - Review this report with team
   - Prioritize refactoring items based on business needs
   - Decide on phased vs. all-at-once approach

2. **Set Up Testing Infrastructure**
   - Ensure test coverage is adequate
   - Add any missing integration tests
   - Set up test database for refactoring

3. **Create Feature Branch**
   ```bash
   git checkout -b refactor/eliminate-duplicate-code
   ```

4. **Start with High-Priority, Low-Risk Items**
   - Begin with session ownership verification
   - This has highest security impact and lowest risk

### Success Criteria

- [ ] Code duplication rate reduced to <5%
- [ ] All tests passing (unit, integration, contract)
- [ ] No performance regression
- [ ] No security regressions
- [ ] Code review approved
- [ ] Documentation updated

---

## Appendix A: Files Requiring Changes

### Files to Create (New)
1. `/src/api/dependencies.py`
2. `/src/api/error_handlers.py`
3. `/src/utils/database_helpers.py`
4. `/src/utils/pagination.py`
5. `/src/utils/redis_helpers.py`

### Files to Modify (High Priority)
1. `/src/api/sessions.py` - 16 changes
2. `/src/api/steps.py` - 15 changes
3. `/src/api/progress.py` - 4 changes
4. `/src/services/abuse_detection.py` - 8 changes
5. `/src/middleware/rate_limiter.py` - 2 changes
6. `/src/api/guides.py` - 2 changes
7. `/src/api/admin.py` - 6 changes

### Files to Modify (Medium Priority)
8. `/src/api/auth.py` - 3 changes
9. `/src/auth/middleware.py` - 4 changes
10. `/src/services/guide_service.py` - 4 changes
11. `/src/services/session_service.py` - 6 changes
12. `/src/services/step_service.py` - 2 changes

**Total Files Affected:** 17 files (12 modified, 5 new)

---

## Appendix B: Testing Checklist

### Unit Tests Required
- [ ] Test `verify_session_ownership()` with valid/invalid sessions
- [ ] Test `verify_user_match()` with matching/non-matching users
- [ ] Test `handle_api_errors()` with all exception types
- [ ] Test `commit_and_refresh()` with successful/failed commits
- [ ] Test `with_redis_fallback()` with available/unavailable Redis
- [ ] Test `paginate()` with various page sizes and data sets

### Integration Tests Required
- [ ] Test session endpoints with refactored ownership checks
- [ ] Test step endpoints with refactored error handling
- [ ] Test admin endpoints with refactored pagination
- [ ] Test abuse detection with refactored Redis calls
- [ ] Test rate limiting with refactored Redis calls

### Security Tests Required
- [ ] Verify session ownership is enforced in all endpoints
- [ ] Test unauthorized access attempts
- [ ] Test privilege escalation attempts
- [ ] Verify error messages don't leak sensitive information

---

**Report End**
