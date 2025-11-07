"""Guide adaptation service for handling impossible steps and generating alternatives."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.database import GuideSessionModel, StepGuideModel
from ..utils.logging import get_logger
from .llm_service import LLMService

logger = get_logger(__name__)


class GuideAdaptationService:
    """Service for adapting guides when steps become impossible."""

    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service

    async def handle_impossible_step(
        self,
        session_id: UUID,
        problem_description: str,
        reason: str,
        what_user_sees: str | None = None,
        attempted_solutions: list[str] | None = None,
        db: AsyncSession = None,
    ) -> dict[str, Any]:
        """Handle a step that has become impossible and generate alternatives.

        Args:
            session_id: The session ID
            problem_description: Description of the problem
            reason: Reason category (ui_changed, feature_missing, access_denied, other)
            what_user_sees: What the user actually sees in their environment
            attempted_solutions: What the user has already tried
            db: Database session

        Returns:
            Dictionary with blocked step info and alternative steps
        """
        logger.info(
            "adaptation_started",
            session_id=str(session_id),
            problem=problem_description,
            reason=reason,
        )

        try:
            # Get session and guide
            session = await self._get_session(session_id, db)
            guide = await self._get_guide(session.guide_id, db)

            # Build adaptation context
            context = await self.build_adaptation_context(
                session=session,
                guide=guide,
                problem_description=problem_description,
                reason=reason,
                what_user_sees=what_user_sees,
                attempted_solutions=attempted_solutions,
            )

            # Generate alternative steps using LLM
            alternative_steps_data = await self.request_alternative_steps(context)

            # Merge alternatives into guide structure
            # This returns the updated guide_data AND the list of created alternative step identifiers
            updated_guide_data, alternative_identifiers = (
                await self.merge_alternatives_into_guide(
                    guide_data=guide.guide_data,
                    current_step_identifier=session.current_step_identifier,
                    blocked_reason=problem_description,
                    alternative_steps=alternative_steps_data["alternative_steps"],
                )
            )

            # Update guide in database
            await self._update_guide_with_adaptation(
                guide=guide,
                updated_guide_data=updated_guide_data,
                adaptation_info={
                    "timestamp": datetime.utcnow().isoformat(),
                    "blocked_step_identifier": session.current_step_identifier,
                    "blocked_reason": problem_description,
                    "reason_category": reason,
                    "alternatives_added": alternative_identifiers,  # Use the identifiers created during merge
                    "llm_provider": alternative_steps_data.get("provider", "unknown"),
                },
                db=db,
            )

            # Update session to point to first alternative
            first_alternative_id = alternative_identifiers[0]
            await self._update_session_step(session_id, first_alternative_id, db)

            # Get the alternative steps from updated guide for return value
            alternative_steps_with_ids = [
                self._find_step_by_identifier(updated_guide_data, alt_id)
                for alt_id in alternative_identifiers
            ]

            logger.info(
                "adaptation_completed",
                session_id=str(session_id),
                alternatives_count=len(alternative_identifiers),
                provider=alternative_steps_data.get("provider", "unknown"),
                generation_time=alternative_steps_data.get("generation_time", 0),
            )

            # Return response
            return {
                "status": "adapted",
                "message": "Alternative approach generated successfully",
                "blocked_step": self._find_step_by_identifier(
                    updated_guide_data, session.current_step_identifier
                ),
                "alternative_steps": alternative_steps_with_ids,
                "current_step": self._find_step_by_identifier(
                    updated_guide_data, first_alternative_id
                ),
            }

        except Exception as e:
            logger.error(
                "adaptation_failed",
                session_id=str(session_id),
                error=str(e),
                error_type=type(e).__name__,
            )
            raise

    async def build_adaptation_context(
        self,
        session: GuideSessionModel,
        guide: StepGuideModel,
        problem_description: str,
        reason: str,
        what_user_sees: str | None,
        attempted_solutions: list[str] | None,
    ) -> dict[str, Any]:
        """Build context for LLM adaptation prompt."""

        guide_data = guide.guide_data
        current_step_id = session.current_step_identifier

        # Extract completed steps
        completed_steps = self._get_completed_steps(guide_data, current_step_id)

        # Get current blocked step
        blocked_step = self._find_step_by_identifier(guide_data, current_step_id)

        # Get remaining goal
        remaining_steps = self._get_remaining_steps(guide_data, current_step_id)

        return {
            "original_goal": guide.title,
            "guide_description": guide.description,
            "completed_steps": completed_steps,
            "blocked_step": blocked_step,
            "remaining_steps_count": len(remaining_steps),
            "problem": {
                "description": problem_description,
                "reason": reason,
                "what_user_sees": what_user_sees or "Not specified",
                "attempted_solutions": attempted_solutions or [],
            },
        }

    async def request_alternative_steps(
        self, context: dict[str, Any]
    ) -> dict[str, Any]:
        """Request alternative steps from LLM service."""

        # Generate alternatives using LLM
        result, provider, generation_time = (
            await self.llm_service.generate_step_alternatives(
                original_goal=context["original_goal"],
                completed_steps=context["completed_steps"],
                blocked_step=context["blocked_step"],
                problem=context["problem"],
            )
        )

        return {
            "alternative_steps": result.get("alternative_steps", []),
            "reason_for_change": result.get("reason_for_change", ""),
            "provider": provider,
            "generation_time": generation_time,
        }

    async def merge_alternatives_into_guide(
        self,
        guide_data: dict[str, Any],
        current_step_identifier: str,
        blocked_reason: str,
        alternative_steps: list[dict[str, Any]],
    ) -> tuple[dict[str, Any], list[str]]:
        """Merge alternative steps into the guide structure.

        This will:
        1. Mark the current step as blocked
        2. Insert alternative steps with sub-indices (e.g., "1a", "1b")
        3. Maintain proper ordering

        Returns:
            tuple: (updated_guide_data, list of alternative step identifiers)
        """

        # Deep copy to avoid mutation
        import copy

        updated_guide_data = copy.deepcopy(guide_data)

        sections = updated_guide_data.get("sections", [])
        alternative_identifiers = []

        # Find the section containing the blocked step
        for section in sections:
            steps = section.get("steps", [])
            for i, step in enumerate(steps):
                if (
                    step.get("step_identifier") == current_step_identifier
                    or str(step.get("step_index")) == current_step_identifier
                ):

                    # Mark step as blocked
                    step["status"] = "blocked"
                    step["blocked_reason"] = blocked_reason
                    step["show_as"] = "crossed_out"

                    # Generate sub-indices for alternatives
                    base_identifier = current_step_identifier
                    letters = ["a", "b", "c", "d", "e", "f"]

                    # Create alternative steps with proper identifiers
                    alternatives_to_insert = []
                    for idx, alt_step in enumerate(alternative_steps):
                        if idx < len(letters):
                            alt_identifier = f"{base_identifier}{letters[idx]}"
                            alternative_identifiers.append(alt_identifier)

                            alternative_step = {
                                "step_identifier": alt_identifier,
                                "step_index": step.get(
                                    "step_index"
                                ),  # Same numeric index
                                "title": alt_step["title"],
                                "description": alt_step["description"],
                                "completion_criteria": alt_step["completion_criteria"],
                                "assistance_hints": alt_step.get(
                                    "assistance_hints", []
                                ),
                                "estimated_duration_minutes": alt_step.get(
                                    "estimated_duration_minutes", 5
                                ),
                                "requires_desktop_monitoring": alt_step.get(
                                    "requires_desktop_monitoring", False
                                ),
                                "visual_markers": alt_step.get("visual_markers", []),
                                "prerequisites": alt_step.get("prerequisites", []),
                                "status": "alternative",
                                "replaces_step_identifier": current_step_identifier,
                                "completed": False,
                                "needs_assistance": False,
                            }
                            alternatives_to_insert.append(alternative_step)

                    # Insert alternatives right after the blocked step
                    for idx, alt in enumerate(alternatives_to_insert):
                        steps.insert(i + 1 + idx, alt)

                    break

        return updated_guide_data, alternative_identifiers

    async def _update_guide_with_adaptation(
        self,
        guide: StepGuideModel,
        updated_guide_data: dict[str, Any],
        adaptation_info: dict[str, Any],
        db: AsyncSession,
    ):
        """Update guide in database with adaptation."""

        # Update adaptation history
        adaptation_history = guide.adaptation_history or []
        adaptation_history.append(adaptation_info)

        # Update guide
        update_query = (
            update(StepGuideModel)
            .where(StepGuideModel.guide_id == guide.guide_id)
            .values(
                guide_data=updated_guide_data,
                adaptation_history=adaptation_history,
                last_adapted_at=datetime.utcnow(),
            )
        )

        await db.execute(update_query)
        await db.commit()

    async def _update_session_step(
        self, session_id: UUID, new_step_identifier: str, db: AsyncSession
    ):
        """Update session to point to new step."""

        update_query = (
            update(GuideSessionModel)
            .where(GuideSessionModel.session_id == session_id)
            .values(
                current_step_identifier=new_step_identifier,
                updated_at=datetime.utcnow(),
            )
        )

        await db.execute(update_query)
        await db.commit()

    async def _get_session(
        self, session_id: UUID, db: AsyncSession
    ) -> GuideSessionModel:
        """Get session from database."""
        query = select(GuideSessionModel).where(
            GuideSessionModel.session_id == session_id
        )
        result = await db.execute(query)
        session = result.scalar_one_or_none()

        if not session:
            raise ValueError(f"Session {session_id} not found")

        return session

    async def _get_guide(self, guide_id: UUID, db: AsyncSession) -> StepGuideModel:
        """Get guide from database."""
        query = select(StepGuideModel).where(StepGuideModel.guide_id == guide_id)
        result = await db.execute(query)
        guide = result.scalar_one_or_none()

        if not guide:
            raise ValueError(f"Guide {guide_id} not found")

        return guide

    def _find_step_by_identifier(
        self, guide_data: dict[str, Any], step_identifier: str
    ) -> dict[str, Any] | None:
        """Find a step by its identifier."""
        sections = guide_data.get("sections", [])

        for section in sections:
            for step in section.get("steps", []):
                if (
                    step.get("step_identifier") == step_identifier
                    or str(step.get("step_index")) == step_identifier
                ):
                    return step

        return None

    def _get_completed_steps(
        self, guide_data: dict[str, Any], current_step_id: str
    ) -> list[dict[str, Any]]:
        """Get all steps completed before current step."""
        completed = []
        sections = guide_data.get("sections", [])

        for section in sections:
            for step in section.get("steps", []):
                step_id = step.get("step_identifier", str(step.get("step_index")))
                if self._is_step_before(step_id, current_step_id):
                    completed.append(
                        {
                            "title": step.get("title"),
                            "identifier": step_id,
                            "description": step.get("description", "")[
                                :100
                            ],  # Truncate
                        }
                    )

        return completed

    def _get_remaining_steps(
        self, guide_data: dict[str, Any], current_step_id: str
    ) -> list[dict[str, Any]]:
        """Get all steps after current step."""
        remaining = []
        sections = guide_data.get("sections", [])
        found_current = False

        for section in sections:
            for step in section.get("steps", []):
                step_id = step.get("step_identifier", str(step.get("step_index")))
                if found_current:
                    remaining.append(step)
                elif step_id == current_step_id:
                    found_current = True

        return remaining

    def _is_step_before(self, step_id1: str, step_id2: str) -> bool:
        """Check if step_id1 comes before step_id2 using natural sort."""
        import re

        def natural_sort_key(s):
            """Convert string to list of ints and strings for natural sorting."""
            return [
                int(text) if text.isdigit() else text.lower()
                for text in re.split("([0-9]+)", s)
            ]

        return natural_sort_key(step_id1) < natural_sort_key(step_id2)
