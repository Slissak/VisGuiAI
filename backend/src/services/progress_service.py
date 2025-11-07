"""Progress tracking service for real-time session monitoring."""

import uuid
from datetime import datetime, timedelta
from typing import Any

from fastapi import Depends
from shared.schemas.api_responses import ProgressResponse
from shared.schemas.progress_tracker import ProgressUpdate
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.redis import SessionStore, get_session_store
from ..models.database import GuideSessionModel, ProgressTrackerModel, StepModel


class ProgressNotFoundError(Exception):
    """Exception raised when progress tracker is not found."""

    pass


class ProgressService:
    """Service for real-time progress tracking and time estimation."""

    def __init__(self, session_store: SessionStore):
        self.session_store = session_store

    async def get_progress(
        self, session_id: uuid.UUID, db: AsyncSession
    ) -> ProgressResponse | None:
        """Get current progress for a session."""

        # Try cache first
        cached_progress = await self._get_cached_progress(session_id)
        if cached_progress:
            return cached_progress

        # Fetch from database
        progress_query = select(ProgressTrackerModel).where(
            ProgressTrackerModel.session_id == session_id
        )
        progress_result = await db.execute(progress_query)
        progress_model = progress_result.scalar_one_or_none()

        if not progress_model:
            return None

        # Get session for additional context
        session_query = select(GuideSessionModel).where(
            GuideSessionModel.session_id == session_id
        )
        session_result = await db.execute(session_query)
        session_model = session_result.scalar_one_or_none()

        if not session_model:
            return None

        # Build response
        progress_response = ProgressResponse(
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
            session_status=session_model.status,
        )

        # Cache the result
        await self._cache_progress(progress_response)

        return progress_response

    async def update_progress(
        self, session_id: uuid.UUID, update: ProgressUpdate, db: AsyncSession
    ) -> ProgressResponse:
        """Update progress tracker with new data."""

        # Get current progress tracker
        progress_query = select(ProgressTrackerModel).where(
            ProgressTrackerModel.session_id == session_id
        )
        progress_result = await db.execute(progress_query)
        progress_model = progress_result.scalar_one_or_none()

        if not progress_model:
            raise ProgressNotFoundError(
                f"Progress tracker for session {session_id} not found"
            )

        # Calculate time spent
        current_time = datetime.utcnow()
        time_spent = progress_model.time_spent_minutes

        if update.time_spent_minutes is not None:
            time_spent = update.time_spent_minutes
        else:
            # Calculate time since last activity
            if progress_model.last_activity_at:
                time_delta = current_time - progress_model.last_activity_at
                time_spent += time_delta.total_seconds() / 60

        # Prepare update data
        update_data = {
            "time_spent_minutes": time_spent,
            "last_activity_at": current_time,
        }

        if update.current_step_id is not None:
            update_data["current_step_id"] = update.current_step_id

        if update.estimated_time_remaining_minutes is not None:
            update_data["estimated_time_remaining_minutes"] = (
                update.estimated_time_remaining_minutes
            )

        # Apply updates
        update_query = (
            update(ProgressTrackerModel)
            .where(ProgressTrackerModel.session_id == session_id)
            .values(**update_data)
        )

        await db.execute(update_query)
        await db.commit()

        # Refresh model
        await db.refresh(progress_model)

        # Get session status
        session_query = select(GuideSessionModel).where(
            GuideSessionModel.session_id == session_id
        )
        session_result = await db.execute(session_query)
        session_model = session_result.scalar_one()

        # Build response
        progress_response = ProgressResponse(
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
            session_status=session_model.status,
        )

        # Update cache
        await self._cache_progress(progress_response)

        return progress_response

    async def calculate_time_estimates(
        self, session_id: uuid.UUID, db: AsyncSession
    ) -> dict[str, float]:
        """Calculate updated time estimates based on actual completion times."""

        # Get progress tracker
        progress_query = select(ProgressTrackerModel).where(
            ProgressTrackerModel.session_id == session_id
        )
        progress_result = await db.execute(progress_query)
        progress_model = progress_result.scalar_one_or_none()

        if not progress_model:
            raise ProgressNotFoundError(
                f"Progress tracker for session {session_id} not found"
            )

        # Get session and guide info
        session_query = select(GuideSessionModel).where(
            GuideSessionModel.session_id == session_id
        )
        session_result = await db.execute(session_query)
        session_result.scalar_one()

        # Get remaining steps with their estimated durations
        remaining_step_ids = [
            uuid.UUID(step_id) for step_id in progress_model.remaining_steps
        ]

        if remaining_step_ids:
            steps_query = select(StepModel).where(
                StepModel.step_id.in_(remaining_step_ids)
            )
            steps_result = await db.execute(steps_query)
            remaining_steps = steps_result.scalars().all()

            base_remaining_time = sum(
                step.estimated_duration_minutes for step in remaining_steps
            )
        else:
            base_remaining_time = 0

        # Calculate completion rate adjustment
        completed_count = len(progress_model.completed_steps)
        if completed_count > 0:
            # Use actual time vs estimated time to adjust future estimates
            avg_time_per_step = progress_model.time_spent_minutes / completed_count
            # Apply a learning factor - if user is consistently faster/slower, adjust
            remaining_adjusted = len(progress_model.remaining_steps) * avg_time_per_step
        else:
            remaining_adjusted = base_remaining_time

        # Conservative estimate (take max of base and adjusted)
        estimated_remaining = max(base_remaining_time, remaining_adjusted)

        return {
            "estimated_time_remaining_minutes": estimated_remaining,
            "base_estimate_minutes": base_remaining_time,
            "adjusted_estimate_minutes": remaining_adjusted,
            "average_time_per_completed_step": (
                progress_model.time_spent_minutes / completed_count
                if completed_count > 0
                else 0
            ),
        }

    async def get_session_analytics(
        self, session_id: uuid.UUID, db: AsyncSession
    ) -> dict[str, Any]:
        """Get detailed analytics for a session."""

        progress = await self.get_progress(session_id, db)
        if not progress:
            raise ProgressNotFoundError(
                f"Progress tracker for session {session_id} not found"
            )

        time_estimates = await self.calculate_time_estimates(session_id, db)

        # Calculate session metrics
        total_steps = len(progress.completed_steps) + len(progress.remaining_steps)
        session_duration = datetime.utcnow() - progress.started_at

        analytics = {
            "session_overview": {
                "total_steps": total_steps,
                "completed_steps": len(progress.completed_steps),
                "remaining_steps": len(progress.remaining_steps),
                "completion_percentage": progress.completion_percentage,
                "session_duration_minutes": session_duration.total_seconds() / 60,
                "active_time_minutes": progress.time_spent_minutes,
            },
            "time_analysis": time_estimates,
            "efficiency_metrics": {
                "steps_per_hour": (
                    len(progress.completed_steps) / (progress.time_spent_minutes / 60)
                    if progress.time_spent_minutes > 0
                    else 0
                ),
                "estimated_completion_time": (
                    progress.started_at
                    + timedelta(
                        minutes=progress.time_spent_minutes
                        + time_estimates["estimated_time_remaining_minutes"]
                    )
                ).isoformat(),
            },
            "status": {
                "current_step_id": (
                    str(progress.current_step_id) if progress.current_step_id else None
                ),
                "session_status": progress.session_status.value,
                "last_activity": progress.last_activity_at.isoformat(),
            },
        }

        return analytics

    async def _get_cached_progress(
        self, session_id: uuid.UUID
    ) -> ProgressResponse | None:
        """Get progress data from cache."""
        cache_key = f"progress:{session_id}"
        cached_data = await self.session_store.get_session(cache_key)

        if not cached_data:
            return None

        try:
            # Convert cached data back to ProgressResponse
            return ProgressResponse(**cached_data)
        except Exception:
            # If cache data is invalid, return None to fall back to database
            return None

    async def _cache_progress(self, progress: ProgressResponse):
        """Cache progress data for faster retrieval."""
        cache_key = f"progress:{progress.session_id}"

        # Convert to dict for caching
        progress_data = {
            "tracker_id": str(progress.tracker_id),
            "session_id": str(progress.session_id),
            "completed_steps": progress.completed_steps,
            "current_step_id": (
                str(progress.current_step_id) if progress.current_step_id else None
            ),
            "remaining_steps": progress.remaining_steps,
            "completion_percentage": progress.completion_percentage,
            "estimated_time_remaining_minutes": progress.estimated_time_remaining_minutes,
            "time_spent_minutes": progress.time_spent_minutes,
            "started_at": progress.started_at.isoformat(),
            "last_activity_at": progress.last_activity_at.isoformat(),
            "session_status": progress.session_status.value,
        }

        await self.session_store.store_session(cache_key, progress_data)


async def get_progress_service(
    session_store: SessionStore = Depends(get_session_store),
) -> ProgressService:
    """Dependency to get progress service."""
    return ProgressService(session_store)
