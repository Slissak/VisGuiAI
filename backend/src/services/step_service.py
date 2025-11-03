"""Step completion service with dual detection methods."""

import uuid
from typing import Optional, List
from datetime import datetime

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from shared.schemas.step import Step
from shared.schemas.guide_session import CompletionMethod
from shared.schemas.api_responses import StepCompletionRequest, StepResponse

from ..models.database import (
    StepModel, GuideSessionModel, CompletionEventModel, ProgressTrackerModel
)
from ..core.redis import SessionStore, get_session_store


class StepNotFoundError(Exception):
    """Exception raised when step is not found."""
    pass


class InvalidStepStateError(Exception):
    """Exception raised when step state transition is invalid."""
    pass


class StepService:
    """Service for managing step completion with dual detection methods."""

    def __init__(self, session_store: SessionStore):
        self.session_store = session_store

    async def complete_step(
        self,
        session_id: uuid.UUID,
        step_id: uuid.UUID,
        request: StepCompletionRequest,
        db: AsyncSession
    ) -> StepResponse:
        """Complete a step using either manual or desktop monitoring method."""

        # Verify session exists and get completion method
        session_query = select(GuideSessionModel).where(
            GuideSessionModel.session_id == session_id
        )
        session_result = await db.execute(session_query)
        session_model = session_result.scalar_one_or_none()

        if not session_model:
            raise ValueError(f"Session {session_id} not found")

        # Get step model
        step_query = select(StepModel).where(StepModel.step_id == step_id)
        step_result = await db.execute(step_query)
        step_model = step_result.scalar_one_or_none()

        if not step_model:
            raise StepNotFoundError(f"Step {step_id} not found")

        # Validate completion method matches session
        if session_model.completion_method == CompletionMethod.DESKTOP_MONITORING:
            if not request.detected_via_monitoring:
                raise InvalidStepStateError(
                    "Session requires desktop monitoring but step was manually completed"
                )
        elif session_model.completion_method == CompletionMethod.MANUAL:
            if request.detected_via_monitoring:
                raise InvalidStepStateError(
                    "Session requires manual completion but step was auto-detected"
                )

        # Create completion event
        completion_event = CompletionEventModel(
            event_id=uuid.uuid4(),
            session_id=session_id,
            step_id=step_id,
            detected_via_monitoring=request.detected_via_monitoring,
            completion_timestamp=datetime.utcnow(),
            visual_evidence_path=request.visual_evidence_path,
            user_confirmation=request.user_confirmation,
            desktop_state_snapshot=request.desktop_state_snapshot or {}
        )

        db.add(completion_event)

        # Update progress tracker
        await self._update_progress_tracker(session_id, step_id, db)

        # Update session current step if this is the current step
        if session_model.current_step_index == step_model.step_index:
            # Advance to next step
            next_step_index = step_model.step_index + 1
            await db.execute(
                update(GuideSessionModel)
                .where(GuideSessionModel.session_id == session_id)
                .values(
                    current_step_index=next_step_index,
                    updated_at=datetime.utcnow()
                )
            )

        await db.commit()

        # Update cache
        return StepResponse(
            step_id=step_id,
            guide_id=step_model.guide_id,
            step_index=step_model.step_index,
            title=step_model.title,
            description=step_model.description,
            completion_criteria=step_model.completion_criteria,
            assistance_hints=step_model.assistance_hints,
            estimated_duration_minutes=step_model.estimated_duration_minutes,
            requires_desktop_monitoring=step_model.requires_desktop_monitoring,
            visual_markers=step_model.visual_markers,
            dependencies=step_model.dependencies,
            completed=True,
            needs_assistance=False,
            is_current=False,
            can_complete=False
        )

    async def mark_needs_assistance(
        self,
        step_id: uuid.UUID,
        session_id: uuid.UUID,
        needs_assistance: bool,
        db: AsyncSession
    ) -> StepResponse:
        """Mark a step as needing assistance."""

        # Get step model
        step_query = select(StepModel).where(StepModel.step_id == step_id)
        step_result = await db.execute(step_query)
        step_model = step_result.scalar_one_or_none()

        if not step_model:
            raise StepNotFoundError(f"Step {step_id} not found")

        # Update cache with assistance flag
        await self._update_step_assistance_cache(session_id, step_id, needs_assistance)

        # Check if step is completed (from completion events)
        completion_query = select(CompletionEventModel).where(
            CompletionEventModel.step_id == step_id,
            CompletionEventModel.session_id == session_id
        )
        completion_result = await db.execute(completion_query)
        is_completed = completion_result.scalar_one_or_none() is not None

        return StepResponse(
            step_id=step_id,
            guide_id=step_model.guide_id,
            step_index=step_model.step_index,
            title=step_model.title,
            description=step_model.description,
            completion_criteria=step_model.completion_criteria,
            assistance_hints=step_model.assistance_hints,
            estimated_duration_minutes=step_model.estimated_duration_minutes,
            requires_desktop_monitoring=step_model.requires_desktop_monitoring,
            visual_markers=step_model.visual_markers,
            dependencies=step_model.dependencies,
            completed=is_completed,
            needs_assistance=needs_assistance,
            is_current=False,
            can_complete=True
        )

    async def get_session_steps(
        self,
        session_id: uuid.UUID,
        db: AsyncSession
    ) -> List[StepResponse]:
        """Get all steps for a session with completion status."""

        # Get session to find guide_id
        session_query = select(GuideSessionModel).where(
            GuideSessionModel.session_id == session_id
        )
        session_result = await db.execute(session_query)
        session_model = session_result.scalar_one_or_none()

        if not session_model:
            raise ValueError(f"Session {session_id} not found")

        # Get all steps for the guide
        steps_query = select(StepModel).where(
            StepModel.guide_id == session_model.guide_id
        ).order_by(StepModel.step_index)
        steps_result = await db.execute(steps_query)
        step_models = steps_result.scalars().all()

        # Get completion events for this session
        completion_query = select(CompletionEventModel).where(
            CompletionEventModel.session_id == session_id
        )
        completion_result = await db.execute(completion_query)
        completed_step_ids = {event.step_id for event in completion_result.scalars().all()}

        # Build step responses
        step_responses = []
        for step_model in step_models:
            is_completed = step_model.step_id in completed_step_ids

            # Check cache for assistance flag
            needs_assistance = await self._get_step_assistance_from_cache(
                session_id, step_model.step_id
            )

            step_responses.append(StepResponse(
                step_id=step_model.step_id,
                guide_id=step_model.guide_id,
                step_index=step_model.step_index,
                title=step_model.title,
                description=step_model.description,
                completion_criteria=step_model.completion_criteria,
                assistance_hints=step_model.assistance_hints,
                estimated_duration_minutes=step_model.estimated_duration_minutes,
                requires_desktop_monitoring=step_model.requires_desktop_monitoring,
                visual_markers=step_model.visual_markers,
                dependencies=step_model.dependencies,
                completed=is_completed,
                needs_assistance=needs_assistance,
                is_current=session_model.current_step_identifier == step_model.step_identifier,
                can_complete=True
            ))

        return step_responses

    async def _update_progress_tracker(
        self,
        session_id: uuid.UUID,
        completed_step_id: uuid.UUID,
        db: AsyncSession
    ):
        """Update progress tracker when a step is completed."""

        # Get current progress tracker
        progress_query = select(ProgressTrackerModel).where(
            ProgressTrackerModel.session_id == session_id
        )
        progress_result = await db.execute(progress_query)
        progress_model = progress_result.scalar_one_or_none()

        if not progress_model:
            return

        # Update completed steps list
        completed_steps = progress_model.completed_steps.copy()
        if str(completed_step_id) not in completed_steps:
            completed_steps.append(str(completed_step_id))

        # Update remaining steps
        remaining_steps = progress_model.remaining_steps.copy()
        if str(completed_step_id) in remaining_steps:
            remaining_steps.remove(str(completed_step_id))

        # Calculate completion percentage
        total_steps = len(completed_steps) + len(remaining_steps)
        completion_percentage = (len(completed_steps) / total_steps * 100) if total_steps > 0 else 0

        # Update progress tracker
        update_query = update(ProgressTrackerModel).where(
            ProgressTrackerModel.session_id == session_id
        ).values(
            completed_steps=completed_steps,
            remaining_steps=remaining_steps,
            completion_percentage=completion_percentage,
            last_activity_at=datetime.utcnow()
        )

        await db.execute(update_query)

    async def _update_step_cache(self, session_id: uuid.UUID, step_id: uuid.UUID, completed: bool):
        """Update step completion status in cache."""
        cache_key = f"step:{session_id}:{step_id}"
        step_data = {
            "completed": completed,
            "updated_at": datetime.utcnow().isoformat()
        }
        await self.session_store.store_session(cache_key, step_data)

    async def _update_step_assistance_cache(
        self,
        session_id: uuid.UUID,
        step_id: uuid.UUID,
        needs_assistance: bool
    ):
        """Update step assistance flag in cache."""
        cache_key = f"step_assistance:{session_id}:{step_id}"
        assistance_data = {
            "needs_assistance": needs_assistance,
            "updated_at": datetime.utcnow().isoformat()
        }
        await self.session_store.store_session(cache_key, assistance_data)

    async def _get_step_assistance_from_cache(
        self,
        session_id: uuid.UUID,
        step_id: uuid.UUID
    ) -> bool:
        """Get step assistance flag from cache."""
        cache_key = f"step_assistance:{session_id}:{step_id}"
        cached_data = await self.session_store.get_session(cache_key)
        return cached_data.get("needs_assistance", False) if cached_data else False


async def get_step_service(session_store: SessionStore = Depends(get_session_store)) -> StepService:
    """Dependency to get step service."""
    return StepService(session_store)