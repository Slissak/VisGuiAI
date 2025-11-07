"""Session management service for guide sessions."""

import uuid
from datetime import datetime
from typing import Optional

from shared.schemas.api_responses import (
    SessionCreateRequest,
    SessionDetailResponse,
    SessionResponse,
    SessionUpdateRequest,
)
from shared.schemas.guide_session import CompletionMethod, SessionStatus
from shared.schemas.progress_tracker import ProgressTracker
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..core.redis import SessionStore
from ..exceptions import GuideNotFoundError, SessionNotFoundError, ValidationError
from ..models.database import GuideSessionModel, ProgressTrackerModel, StepGuideModel
from .guide_service import GuideService


class InvalidSessionStateError(ValidationError):
    """Exception raised when session state transition is invalid."""

    def __init__(self, from_status: str, to_status: str):
        super().__init__(
            field="status",
            value=to_status,
            reason=f"Invalid status transition from {from_status} to {to_status}",
        )


class SessionService:
    """Service for managing guide sessions."""

    def __init__(
        self, guide_service: GuideService = None, session_store: SessionStore = None
    ):
        self.guide_service = guide_service
        self.session_store = session_store

    async def create_session(
        self, request: SessionCreateRequest, db: AsyncSession
    ) -> SessionResponse:
        """Create a new guide session."""

        # Verify guide exists
        guide = await self.guide_service.get_guide(request.guide_id, db)
        if not guide:
            raise GuideNotFoundError(str(request.guide_id))

        # Create session
        session_id = uuid.uuid4()
        session_model = GuideSessionModel(
            session_id=session_id,
            user_id=request.user_id,
            guide_id=request.guide_id,
            current_step_identifier="0",
            status=SessionStatus.ACTIVE,
            completion_method=request.completion_method,
            session_metadata={},
        )

        db.add(session_model)

        # Create progress tracker
        progress_tracker = ProgressTrackerModel(
            tracker_id=uuid.uuid4(),
            session_id=session_id,
            completed_steps=[],
            current_step_id=guide.steps[0].step_id if guide.steps else None,
            remaining_steps=[step.step_id for step in guide.steps],
            completion_percentage=0.0,
            estimated_time_remaining_minutes=guide.estimated_duration_minutes,
            time_spent_minutes=0,
            started_at=datetime.utcnow(),
            last_activity_at=datetime.utcnow(),
        )

        db.add(progress_tracker)
        await db.commit()

        # Cache session data in Redis
        await self._cache_session_data(session_model, guide, db)

        # Add to user's active sessions
        await self.session_store.add_user_session(request.user_id, str(session_id))

        return SessionResponse(
            session_id=session_id,
            guide_id=request.guide_id,
            user_id=request.user_id,
            status=SessionStatus.ACTIVE,
            current_step_identifier="0",
            completion_method=request.completion_method,
            created_at=session_model.created_at,
            updated_at=session_model.updated_at,
            completed_at=None,
        )

    async def create_session_simple(
        self, guide_id: uuid.UUID, user_id: str, db: AsyncSession
    ) -> SessionResponse:
        """Create a new guide session with minimal parameters."""

        # Verify guide exists
        # Optimization: Use selectinload to preload steps for session creation
        guide_query = (
            select(StepGuideModel)
            .options(selectinload(StepGuideModel.steps))
            .where(StepGuideModel.guide_id == guide_id)
        )
        guide_result = await db.execute(guide_query)
        guide = guide_result.scalar_one_or_none()

        if not guide:
            raise GuideNotFoundError(str(guide_id))

        # Create session
        session_id = uuid.uuid4()
        session_model = GuideSessionModel(
            session_id=session_id,
            user_id=user_id,
            guide_id=guide_id,
            current_step_identifier="0",  # Start at step 0 (zero-based indexing)
            status=SessionStatus.ACTIVE,
            completion_method=CompletionMethod.MANUAL_CHECKBOX,
            session_metadata={},
        )

        db.add(session_model)

        # Create progress tracker
        progress_tracker = ProgressTrackerModel(
            tracker_id=uuid.uuid4(),
            session_id=session_id,
            completed_steps=[],
            current_step_id=None,  # Will be set based on guide structure
            remaining_steps=[],  # Will be populated based on guide structure
            completion_percentage=0.0,
            estimated_time_remaining_minutes=guide.estimated_duration_minutes,
            time_spent_minutes=0,
            started_at=datetime.utcnow(),
            last_activity_at=datetime.utcnow(),
        )

        db.add(progress_tracker)
        await db.commit()

        return SessionResponse(
            session_id=session_id,
            guide_id=guide_id,
            user_id=user_id,
            status=SessionStatus.ACTIVE,
            current_step_identifier="0",  # Start at step 0 (zero-based indexing)
            completion_method=CompletionMethod.MANUAL_CHECKBOX,
            created_at=session_model.created_at,
            updated_at=session_model.updated_at,
            completed_at=None,
        )

    async def get_session(
        self, session_id: uuid.UUID, db: AsyncSession
    ) -> SessionDetailResponse | None:
        """Get detailed session information."""

        # Try to get from cache first
        cached_data = await self.session_store.get_session(str(session_id))
        if cached_data:
            return self._build_session_detail_from_cache(cached_data)

        # Fetch from database
        query = (
            select(GuideSessionModel)
            .options(
                selectinload(GuideSessionModel.guide).selectinload(
                    StepGuideModel.steps
                ),
                selectinload(GuideSessionModel.progress_tracker),
            )
            .where(GuideSessionModel.session_id == session_id)
        )

        result = await db.execute(query)
        session_model = result.scalar_one_or_none()

        if not session_model:
            return None

        # Build response
        guide = await self.guide_service.get_guide(session_model.guide_id, db)
        current_step = None
        if guide and guide.steps:
            # Find the current step by identifier
            current_step = self._find_step_by_identifier(
                guide.steps, session_model.current_step_identifier
            )

        progress = self._convert_progress_tracker(session_model.progress_tracker)

        session_response = SessionResponse(
            session_id=session_model.session_id,
            guide_id=session_model.guide_id,
            user_id=session_model.user_id,
            status=session_model.status,
            current_step_identifier=session_model.current_step_identifier,
            completion_method=session_model.completion_method,
            created_at=session_model.created_at,
            updated_at=session_model.updated_at,
            completed_at=session_model.completed_at,
        )

        return SessionDetailResponse(
            session=session_response,
            guide=guide,
            current_step=current_step,
            progress=progress,
        )

    async def get_session_simple(
        self, session_id: uuid.UUID, db: AsyncSession
    ) -> GuideSessionModel | None:
        """Get session model directly from database."""
        # Optimization: Use selectinload to preload related guide and progress tracker
        query = (
            select(GuideSessionModel)
            .options(
                selectinload(GuideSessionModel.guide),
                selectinload(GuideSessionModel.progress_tracker),
            )
            .where(GuideSessionModel.session_id == session_id)
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def update_session(
        self, session_id: uuid.UUID, request: SessionUpdateRequest, db: AsyncSession
    ) -> SessionResponse:
        """Update session status."""

        # Get current session
        # Optimization: Use selectinload to preload guide for validation
        query = (
            select(GuideSessionModel)
            .options(selectinload(GuideSessionModel.guide))
            .where(GuideSessionModel.session_id == session_id)
        )
        result = await db.execute(query)
        session_model = result.scalar_one_or_none()

        if not session_model:
            raise SessionNotFoundError(f"Session {session_id} not found")

        # Validate status transition
        if not self._is_valid_status_transition(session_model.status, request.status):
            raise InvalidSessionStateError(
                from_status=str(session_model.status), to_status=str(request.status)
            )

        # Update session
        update_data = {"updated_at": datetime.utcnow()}

        if request.status:
            update_data["status"] = request.status
            if request.status == SessionStatus.COMPLETED:
                update_data["completed_at"] = datetime.utcnow()

        update_query = (
            update(GuideSessionModel)
            .where(GuideSessionModel.session_id == session_id)
            .values(**update_data)
        )

        await db.execute(update_query)
        await db.commit()

        # Refresh the model
        await db.refresh(session_model)

        # Update cache
        await self._update_session_cache(session_model, db)

        return SessionResponse(
            session_id=session_model.session_id,
            guide_id=session_model.guide_id,
            user_id=session_model.user_id,
            status=session_model.status,
            current_step_identifier=session_model.current_step_identifier,
            completion_method=session_model.completion_method,
            created_at=session_model.created_at,
            updated_at=session_model.updated_at,
            completed_at=session_model.completed_at,
        )

    async def get_user_sessions(
        self, user_id: str, db: AsyncSession, status: SessionStatus | None = None
    ) -> list[SessionResponse]:
        """Get user's sessions, optionally filtered by status."""

        # Optimization: Use selectinload to preload guide information for all sessions
        query = (
            select(GuideSessionModel)
            .options(selectinload(GuideSessionModel.guide))
            .where(GuideSessionModel.user_id == user_id)
        )

        if status:
            query = query.where(GuideSessionModel.status == status)

        result = await db.execute(query)
        session_models = result.scalars().all()

        return [
            SessionResponse(
                session_id=session.session_id,
                guide_id=session.guide_id,
                user_id=session.user_id,
                status=session.status,
                current_step_identifier=session.current_step_identifier,
                completion_method=session.completion_method,
                created_at=session.created_at,
                updated_at=session.updated_at,
                completed_at=session.completed_at,
            )
            for session in session_models
        ]

    async def advance_to_next_step(
        self, session_id: uuid.UUID, db: AsyncSession
    ) -> bool:
        """Advance session to the next step."""

        # Get session and guide
        session_detail = await self.get_session(session_id, db)
        if not session_detail:
            raise SessionNotFoundError(f"Session {session_id} not found")

        guide = session_detail.guide
        current_identifier = session_detail.session.current_step_identifier

        # Find next step identifier
        next_identifier = self._get_next_step_identifier(
            guide.steps, current_identifier
        )

        if not next_identifier:
            # No next step, complete the session
            await self.update_session(
                session_id, SessionUpdateRequest(status=SessionStatus.COMPLETED), db
            )
            return False

        # Advance to next step
        update_query = (
            update(GuideSessionModel)
            .where(GuideSessionModel.session_id == session_id)
            .values(
                current_step_identifier=next_identifier, updated_at=datetime.utcnow()
            )
        )

        await db.execute(update_query)
        await db.commit()

        # Update cache
        # Optimization: Use selectinload to preload guide for cache update
        query = (
            select(GuideSessionModel)
            .options(selectinload(GuideSessionModel.guide))
            .where(GuideSessionModel.session_id == session_id)
        )
        result = await db.execute(query)
        session_model = result.scalar_one()
        await self._update_session_cache(session_model, db)

        return True

    def _is_valid_status_transition(
        self, from_status: SessionStatus, to_status: SessionStatus
    ) -> bool:
        """Check if status transition is valid."""
        valid_transitions = {
            SessionStatus.ACTIVE: [
                SessionStatus.PAUSED,
                SessionStatus.COMPLETED,
                SessionStatus.FAILED,
            ],
            SessionStatus.PAUSED: [SessionStatus.ACTIVE, SessionStatus.FAILED],
            SessionStatus.COMPLETED: [],  # Terminal state
            SessionStatus.FAILED: [SessionStatus.ACTIVE],  # Allow restart
        }

        return to_status in valid_transitions.get(from_status, [])

    async def _cache_session_data(
        self, session: GuideSessionModel, guide, db: AsyncSession
    ):
        """Cache session data in Redis."""
        session_data = {
            "session_id": str(session.session_id),
            "user_id": session.user_id,
            "guide_id": str(session.guide_id),
            "current_step_identifier": session.current_step_identifier,
            "status": session.status.value,
            "completion_method": session.completion_method.value,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
            "guide_title": guide.title if guide else None,
            "total_steps": guide.total_steps if guide else 0,
        }

        await self.session_store.store_session(str(session.session_id), session_data)

    async def _update_session_cache(self, session: GuideSessionModel, db: AsyncSession):
        """Update cached session data."""
        # Get existing cache
        cached_data = await self.session_store.get_session(str(session.session_id))
        if cached_data:
            # Update with new data
            cached_data.update(
                {
                    "current_step_identifier": session.current_step_identifier,
                    "status": session.status.value,
                    "updated_at": session.updated_at.isoformat(),
                    "completed_at": (
                        session.completed_at.isoformat()
                        if session.completed_at
                        else None
                    ),
                }
            )
            await self.session_store.store_session(str(session.session_id), cached_data)

    def _convert_progress_tracker(
        self, progress_model: ProgressTrackerModel
    ) -> ProgressTracker:
        """Convert database progress tracker to Pydantic model."""
        if not progress_model:
            return None

        return ProgressTracker(
            tracker_id=progress_model.tracker_id,
            session_id=progress_model.session_id,
            completed_steps=progress_model.completed_steps,
            current_step_id=progress_model.current_step_id,
            remaining_steps=progress_model.remaining_steps,
            completion_percentage=progress_model.completion_percentage,
            estimated_time_remaining_minutes=progress_model.estimated_time_remaining_minutes,
            time_spent_minutes=progress_model.time_spent_minutes,
            started_at=progress_model.started_at,
            last_activity_at=progress_model.last_activity_at,
        )

    def _build_session_detail_from_cache(
        self, cached_data: dict
    ) -> SessionDetailResponse:
        """Build session detail response from cached data."""
        # This is a simplified version - in production, you'd want to cache more data
        # For now, we'll primarily use database queries
        return None

    def _find_step_by_identifier(self, steps: list, identifier: str) -> Optional:
        """Find a step by its identifier.

        Args:
            steps: List of Step objects
            identifier: String identifier (e.g., "0", "1", "1a", "2b")

        Returns:
            The matching Step object or None
        """
        for step in steps:
            # Check both step_identifier and step_index (for backward compatibility)
            if (
                hasattr(step, "step_identifier") and step.step_identifier == identifier
            ) or (hasattr(step, "step_index") and str(step.step_index) == identifier):
                return step
        return None

    def _get_next_step_identifier(
        self, steps: list, current_identifier: str
    ) -> str | None:
        """Get the next step identifier after the current one.

        Args:
            steps: List of Step objects
            current_identifier: Current step identifier

        Returns:
            Next step identifier as string, or None if at the end
        """
        if not steps:
            return None

        # Find current step index in the list
        current_index = None
        for i, step in enumerate(steps):
            if (
                hasattr(step, "step_identifier")
                and step.step_identifier == current_identifier
            ) or (
                hasattr(step, "step_index")
                and str(step.step_index) == current_identifier
            ):
                current_index = i
                break

        # If current step not found or it's the last step
        if current_index is None or current_index >= len(steps) - 1:
            return None

        # Get next step
        next_step = steps[current_index + 1]
        if hasattr(next_step, "step_identifier"):
            return next_step.step_identifier
        elif hasattr(next_step, "step_index"):
            return str(next_step.step_index)

        return None

    def _validate_step_identifier(self, identifier: str) -> bool:
        """Validate step identifier format.

        Valid formats:
        - Simple integers: "0", "1", "2", etc.
        - Sub-indices: "1a", "1b", "2a", etc.
        - Max length: 10 characters

        Args:
            identifier: Step identifier to validate

        Returns:
            True if valid, False otherwise
        """
        if not identifier or len(identifier) > 10:
            return False

        # Check if it matches pattern: digits optionally followed by a letter
        import re

        return bool(re.match(r"^\d+[a-z]?$", identifier))


async def get_session_service() -> SessionService:
    """Dependency to get session service."""
    return SessionService()


# Create a global session service instance
session_service = SessionService()
