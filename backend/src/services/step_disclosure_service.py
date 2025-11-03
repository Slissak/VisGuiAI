"""Step disclosure service for progressive step revelation and information filtering.

This service has been updated to support string-based step identifiers (e.g., "1", "1a", "1b")
to enable guide adaptation with alternative steps. It handles blocked steps and their alternatives.
"""

from typing import Dict, Any, Optional, List, Tuple
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.sql import func

from ..models.database import GuideSessionModel, StepGuideModel, StepStatus
from ..utils.sorting import (
    natural_sort_key,
    sort_step_identifiers,
    is_identifier_before,
    get_next_identifier,
    get_previous_identifier
)
from ..utils.validation import validate_step_identifier
from ..utils.logging import get_logger
from ..exceptions import SessionNotFoundError, GuideNotFoundError
from shared.schemas.step_guide import DifficultyLevel

logger = get_logger(__name__)


class StepDisclosureService:
    """Service for managing progressive step disclosure and information filtering.

    Updated to work with string identifiers and handle blocked/alternative steps.
    """

    @staticmethod
    async def get_current_step_only(
        session_id: UUID,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Get only the current step for a session, filtering out future steps.

        This method now handles:
        - String-based identifiers (e.g., "1", "1a", "1b")
        - Blocked steps (automatically uses first alternative)
        - Alternative steps (marked with status="alternative")
        """
        # Get session with current position
        session_query = select(GuideSessionModel).where(
            GuideSessionModel.session_id == session_id
        )
        session_result = await db.execute(session_query)
        session = session_result.scalar_one_or_none()

        if not session:
            raise SessionNotFoundError(str(session_id))

        # Get the guide with full structure
        guide_query = select(StepGuideModel).where(
            StepGuideModel.guide_id == session.guide_id
        )
        guide_result = await db.execute(guide_query)
        guide = guide_result.scalar_one_or_none()

        if not guide:
            raise GuideNotFoundError(str(session.guide_id))

        guide_data = guide.guide_data

        # Find current step by identifier
        current_step_identifier = session.current_step_identifier
        # Validate step identifier format
        validate_step_identifier(current_step_identifier)
        current_step, current_section = StepDisclosureService._find_step_by_identifier(
            guide_data, current_step_identifier
        )

        # If current step is blocked, find and use first alternative
        if current_step and current_step.get("status") == "blocked":
            alternatives = StepDisclosureService._find_alternatives_for_step(
                guide_data, current_step_identifier
            )
            if alternatives:
                # Use first alternative
                first_alt_id = alternatives[0].get("step_identifier")
                current_step, current_section = StepDisclosureService._find_step_by_identifier(
                    guide_data, first_alt_id
                )
                # Update session to point to alternative
                await StepDisclosureService._update_session_identifier(
                    session_id, first_alt_id, db
                )

        if not current_step or not current_section:
            # Calculate total active steps (excluding blocked)
            all_identifiers = StepDisclosureService._get_all_step_identifiers(
                guide_data, include_blocked=False
            )
            return {
                "session_id": str(session_id),
                "status": "completed",
                "message": "All steps completed",
                "progress": {
                    "total_steps": len(all_identifiers),
                    "completed_steps": len(all_identifiers),
                    "current_step": None,
                    "current_section": None
                }
            }

        # Calculate progress
        progress_info = StepDisclosureService._calculate_progress(
            guide_data, current_step_identifier
        )

        # Filter and return only current step information
        filtered_response = {
            "session_id": str(session_id),
            "status": "active",
            "guide_title": guide_data.get("title", ""),
            "guide_description": guide_data.get("description", ""),
            "current_section": {
                "section_id": current_section["section_id"],
                "section_title": current_section["section_title"],
                "section_description": current_section["section_description"],
                "section_progress": StepDisclosureService._get_section_progress(
                    current_section, current_step_identifier
                )
            },
            "current_step": {
                "step_identifier": current_step.get("step_identifier"),
                "step_index": current_step.get("step_index"),  # Keep for backward compatibility
                "title": current_step["title"],
                "description": current_step["description"],
                "completion_criteria": current_step["completion_criteria"],
                "assistance_hints": current_step["assistance_hints"],
                "estimated_duration_minutes": current_step["estimated_duration_minutes"],
                "requires_desktop_monitoring": current_step.get("requires_desktop_monitoring", False),
                "visual_markers": current_step.get("visual_markers", []),
                "prerequisites_met": StepDisclosureService._check_prerequisites_met(
                    current_step, current_step_identifier
                ),
                "status": current_step.get("status", "active"),
                "is_alternative": current_step.get("status") == "alternative",
                "replaces_step_identifier": current_step.get("replaces_step_identifier")
            },
            "progress": progress_info,
            "navigation": {
                "can_go_back": StepDisclosureService._can_go_back(
                    guide_data, current_step_identifier
                ),
                "can_skip": StepDisclosureService._can_skip_step(current_step),
                "next_section_preview": StepDisclosureService._get_next_section_preview(
                    guide_data, current_section["section_order"]
                ) if StepDisclosureService._is_last_step_in_section(
                    current_section, current_step
                ) else None
            }
        }

        return filtered_response

    @staticmethod
    async def advance_to_next_step(
        session_id: UUID,
        completion_notes: Optional[str] = None,
        db: AsyncSession = None
    ) -> Dict[str, Any]:
        """Advance session to next step after current step completion.

        Now uses string identifier ordering with natural sorting.
        Automatically skips blocked steps.
        """
        # Get current session
        session_query = select(GuideSessionModel).where(
            GuideSessionModel.session_id == session_id
        )
        session_result = await db.execute(session_query)
        session = session_result.scalar_one_or_none()

        if not session:
            raise SessionNotFoundError(str(session_id))

        logger.info(
            "step_advancement_started",
            session_id=str(session_id),
            current_step_identifier=session.current_step_identifier
        )

        # Get guide
        guide_query = select(StepGuideModel).where(
            StepGuideModel.guide_id == session.guide_id
        )
        guide_result = await db.execute(guide_query)
        guide = guide_result.scalar_one_or_none()

        if not guide:
            raise GuideNotFoundError(str(session.guide_id))

        guide_data = guide.guide_data
        current_identifier = session.current_step_identifier

        # Get all active step identifiers (exclude blocked)
        all_identifiers = StepDisclosureService._get_all_step_identifiers(
            guide_data, include_blocked=False
        )

        # Find next step identifier
        next_identifier = get_next_identifier(current_identifier, all_identifiers)

        if next_identifier is None:
            # End of guide
            update_query = update(GuideSessionModel).where(
                GuideSessionModel.session_id == session_id
            ).values(
                status="completed",
                completed_at=func.now(),
                updated_at=func.now()
            )
            await db.execute(update_query)
            await db.commit()

            logger.info(
                "guide_completed",
                session_id=str(session_id),
                last_step_identifier=current_identifier
            )

            return {
                "session_id": str(session_id),
                "status": "completed",
                "message": "Guide completed successfully"
            }

        # Update session to next step
        await StepDisclosureService._update_session_identifier(
            session_id, next_identifier, db
        )

        # Log completion event
        await StepDisclosureService._log_step_completion(
            session_id, current_identifier, completion_notes, db
        )

        logger.info(
            "step_advancement_completed",
            session_id=str(session_id),
            previous_step_identifier=current_identifier,
            next_step_identifier=next_identifier
        )

        # Return the new current step
        return await StepDisclosureService.get_current_step_only(session_id, db)

    @staticmethod
    async def go_back_to_previous_step(
        session_id: UUID,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Go back to previous step if allowed.

        Now uses string identifier ordering with natural sorting.
        """
        session_query = select(GuideSessionModel).where(
            GuideSessionModel.session_id == session_id
        )
        session_result = await db.execute(session_query)
        session = session_result.scalar_one_or_none()

        if not session:
            raise SessionNotFoundError(str(session_id))

        # Get guide
        guide_query = select(StepGuideModel).where(
            StepGuideModel.guide_id == session.guide_id
        )
        guide_result = await db.execute(guide_query)
        guide = guide_result.scalar_one_or_none()

        if not guide:
            raise GuideNotFoundError(str(session.guide_id))

        guide_data = guide.guide_data
        current_identifier = session.current_step_identifier

        # Get all step identifiers (include all for navigation)
        all_identifiers = StepDisclosureService._get_all_step_identifiers(
            guide_data, include_blocked=True
        )

        # Find previous step identifier
        previous_identifier = get_previous_identifier(current_identifier, all_identifiers)

        if previous_identifier is None:
            raise ValueError("Cannot go back further - already at first step")

        # Update session to previous step
        await StepDisclosureService._update_session_identifier(
            session_id, previous_identifier, db
        )

        return await StepDisclosureService.get_current_step_only(session_id, db)

    @staticmethod
    async def get_section_overview(
        session_id: UUID,
        section_id: str,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Get overview of a specific section with step titles (but not full descriptions).

        Updated to show blocked steps with crossed-out styling and alternatives.
        """
        session_query = select(GuideSessionModel).where(
            GuideSessionModel.session_id == session_id
        )
        session_result = await db.execute(session_query)
        session = session_result.scalar_one_or_none()

        if not session:
            raise SessionNotFoundError(str(session_id))

        guide_query = select(StepGuideModel).where(
            StepGuideModel.guide_id == session.guide_id
        )
        guide_result = await db.execute(guide_query)
        guide = guide_result.scalar_one_or_none()

        if not guide:
            raise GuideNotFoundError(str(session.guide_id))

        guide_data = guide.guide_data
        sections = guide_data.get("sections", [])

        target_section = next(
            (s for s in sections if s["section_id"] == section_id), None
        )

        if not target_section:
            from ..exceptions import ValidationError
            raise ValidationError(
                field="section_id",
                value=section_id,
                reason="Section not found in guide"
            )

        current_identifier = session.current_step_identifier

        # Return section overview with step titles only
        step_overview = []
        for step in target_section["steps"]:
            step_id = step.get("step_identifier", str(step.get("step_index")))
            is_completed = is_identifier_before(step_id, current_identifier)
            is_current = step_id == current_identifier
            is_blocked = step.get("status") == "blocked"
            is_alternative = step.get("status") == "alternative"

            step_info = {
                "step_identifier": step_id,
                "step_index": step.get("step_index"),
                "title": step["title"],
                "estimated_duration_minutes": step["estimated_duration_minutes"],
                "completed": is_completed,
                "current": is_current,
                "locked": not is_completed and not is_current,
                "status": step.get("status", "active"),
                "is_blocked": is_blocked,
                "is_alternative": is_alternative,
            }

            if is_blocked:
                step_info["blocked_reason"] = step.get("blocked_reason")
                step_info["show_as"] = "crossed_out"

            if is_alternative:
                step_info["replaces_step_identifier"] = step.get("replaces_step_identifier")

            step_overview.append(step_info)

        return {
            "section_id": target_section["section_id"],
            "section_title": target_section["section_title"],
            "section_description": target_section["section_description"],
            "section_order": target_section["section_order"],
            "step_overview": step_overview,
            "total_estimated_minutes": sum(
                step["estimated_duration_minutes"]
                for step in target_section["steps"]
                if step.get("status") != "blocked"
            )
        }

    # ==================== HELPER METHODS ====================

    @staticmethod
    def _find_step_by_identifier(
        guide_data: Dict[str, Any],
        step_identifier: str
    ) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """Find step and its section by string identifier.

        Args:
            guide_data: The complete guide data structure
            step_identifier: String identifier (e.g., "1", "1a", "2b")

        Returns:
            Tuple of (step_dict, section_dict) or (None, None) if not found
        """
        sections = guide_data.get("sections", [])

        for section in sections:
            for step in section.get("steps", []):
                # Check both step_identifier and fallback to step_index
                print(f"Searching for: {step_identifier}, in step with identifier: {step.get('step_identifier')} and index: {str(step.get('step_index'))}")
                if step.get("step_identifier") == step_identifier or \
                   str(step.get("step_index")) == step_identifier:
                    return step, section

        return None, None

    @staticmethod
    def _get_all_step_identifiers(
        guide_data: Dict[str, Any],
        include_blocked: bool = False
    ) -> List[str]:
        """Get all step identifiers in natural sorted order.

        Args:
            guide_data: The complete guide data structure
            include_blocked: If False, exclude steps with status="blocked"

        Returns:
            Sorted list of step identifier strings
        """
        identifiers = []
        sections = guide_data.get("sections", [])

        for section in sections:
            for step in section.get("steps", []):
                # Skip blocked steps if requested
                if not include_blocked and step.get("status") == "blocked":
                    continue

                step_id = step.get("step_identifier", str(step.get("step_index")))
                identifiers.append(step_id)

        # Sort using natural sorting (handles "1", "1a", "1b", "2", etc.)
        return sort_step_identifiers(identifiers)

    @staticmethod
    def _find_alternatives_for_step(
        guide_data: Dict[str, Any],
        blocked_identifier: str
    ) -> List[Dict[str, Any]]:
        """Find all alternative steps for a blocked step.

        Args:
            guide_data: The complete guide data structure
            blocked_identifier: Identifier of the blocked step

        Returns:
            List of alternative step dictionaries, sorted by identifier
        """
        alternatives = []
        sections = guide_data.get("sections", [])

        for section in sections:
            for step in section.get("steps", []):
                if step.get("status") == "alternative" and \
                   step.get("replaces_step_identifier") == blocked_identifier:
                    alternatives.append(step)

        # Sort alternatives by identifier
        alternative_ids = [s.get("step_identifier", "") for s in alternatives]
        sorted_ids = sort_step_identifiers(alternative_ids)

        # Return alternatives in sorted order
        sorted_alternatives = []
        for identifier in sorted_ids:
            for alt in alternatives:
                if alt.get("step_identifier") == identifier:
                    sorted_alternatives.append(alt)
                    break
        return sorted_alternatives

    @staticmethod
    def _calculate_progress(
        guide_data: Dict[str, Any],
        current_identifier: str
    ) -> Dict[str, Any]:
        """Calculate progress information using string identifiers.

        Args:
            guide_data: The complete guide data structure
            current_identifier: Current step identifier

        Returns:
            Dictionary with progress metrics
        """
        # Get all active identifiers (exclude blocked)
        all_identifiers = StepDisclosureService._get_all_step_identifiers(
            guide_data, include_blocked=False
        )

        # Count completed steps (all before current)
        completed_count = 0
        for identifier in all_identifiers:
            if is_identifier_before(identifier, current_identifier):
                completed_count += 1
            elif identifier == current_identifier:
                break

        total_steps = len(all_identifiers)
        completion_percentage = round(
            (completed_count / total_steps) * 100, 1
        ) if total_steps > 0 else 0

        estimated_remaining = StepDisclosureService._calculate_remaining_time(
            guide_data, current_identifier
        )

        return {
            "total_steps": total_steps,
            "completed_steps": completed_count,
            "completion_percentage": completion_percentage,
            "estimated_time_remaining": estimated_remaining
        }

    @staticmethod
    def _calculate_remaining_time(
        guide_data: Dict[str, Any],
        current_identifier: str
    ) -> int:
        """Calculate estimated remaining time in minutes.

        Only counts active and alternative steps (not blocked).

        Args:
            guide_data: The complete guide data structure
            current_identifier: Current step identifier

        Returns:
            Estimated remaining time in minutes
        """
        remaining_time = 0
        found_current = False
        sections = guide_data.get("sections", [])

        for section in sections:
            for step in section.get("steps", []):
                # Skip blocked steps
                if step.get("status") == "blocked":
                    continue

                step_id = step.get("step_identifier", str(step.get("step_index")))

                # Once we find current step, start counting
                if step_id == current_identifier:
                    found_current = True
                    continue

                # Add duration for remaining steps
                if found_current:
                    remaining_time += step.get("estimated_duration_minutes", 0)

        return remaining_time

    @staticmethod
    def _get_section_progress(
        section: Dict[str, Any],
        current_identifier: str
    ) -> Dict[str, Any]:
        """Get progress information for current section.

        Args:
            section: Section dictionary
            current_identifier: Current step identifier

        Returns:
            Dictionary with section progress metrics
        """
        section_steps = section.get("steps", [])

        # Count only active and alternative steps
        total_in_section = sum(
            1 for step in section_steps
            if step.get("status") != "blocked"
        )

        # Count completed steps in section
        completed_in_section = 0
        for step in section_steps:
            if step.get("status") == "blocked":
                continue

            step_id = step.get("step_identifier", str(step.get("step_index")))
            if is_identifier_before(step_id, current_identifier):
                completed_in_section += 1

        completion_percentage = round(
            (completed_in_section / total_in_section) * 100, 1
        ) if total_in_section > 0 else 0

        return {
            "completed_steps": completed_in_section,
            "total_steps": total_in_section,
            "completion_percentage": completion_percentage
        }

    @staticmethod
    def _check_prerequisites_met(
        step: Dict[str, Any],
        current_identifier: str
    ) -> bool:
        """Check if step prerequisites are met.

        Args:
            step: Step dictionary
            current_identifier: Current step identifier

        Returns:
            True if prerequisites are met
        """
        prerequisites = step.get("prerequisites", [])
        if not prerequisites:
            return True

        # For simplicity, assume prerequisites are met if we've reached this step
        # In a full implementation, this would check if prerequisite steps are completed
        return True

    @staticmethod
    def _can_skip_step(step: Dict[str, Any]) -> bool:
        """Determine if step can be skipped.

        Args:
            step: Step dictionary

        Returns:
            True if step can be skipped
        """
        # Don't allow skipping steps that require desktop monitoring
        # Don't allow skipping alternative steps (they're already workarounds)
        if step.get("requires_desktop_monitoring", False):
            return False
        if step.get("status") == "alternative":
            return False

        return True

    @staticmethod
    def _can_go_back(
        guide_data: Dict[str, Any],
        current_identifier: str
    ) -> bool:
        """Check if user can navigate back to previous step.

        Args:
            guide_data: The complete guide data structure
            current_identifier: Current step identifier

        Returns:
            True if can go back
        """
        all_identifiers = StepDisclosureService._get_all_step_identifiers(
            guide_data, include_blocked=True
        )

        if not all_identifiers:
            return False

        # Can't go back if at first step
        return current_identifier != all_identifiers[0]

    @staticmethod
    def _is_last_step_in_section(
        section: Dict[str, Any],
        current_step: Dict[str, Any]
    ) -> bool:
        """Check if current step is last in its section.

        Args:
            section: Section dictionary
            current_step: Current step dictionary

        Returns:
            True if current step is last in section
        """
        section_steps = section.get("steps", [])
        if not section_steps:
            return False

        # Get last non-blocked step in section
        active_steps = [
            step for step in section_steps
            if step.get("status") != "blocked"
        ]

        if not active_steps:
            return False

        last_step_id = active_steps[-1].get(
            "step_identifier",
            str(active_steps[-1].get("step_index"))
        )
        current_step_id = current_step.get(
            "step_identifier",
            str(current_step.get("step_index"))
        )

        return last_step_id == current_step_id

    @staticmethod
    def _get_next_section_preview(
        guide_data: Dict[str, Any],
        current_section_order: int
    ) -> Optional[Dict[str, Any]]:
        """Get preview of next section if available.

        Args:
            guide_data: The complete guide data structure
            current_section_order: Order of current section

        Returns:
            Dictionary with next section preview or None
        """
        sections = guide_data.get("sections", [])
        next_section = next(
            (s for s in sections if s.get("section_order") == current_section_order + 1),
            None
        )

        if next_section:
            # Count only active steps
            active_steps = [
                step for step in next_section.get("steps", [])
                if step.get("status") != "blocked"
            ]

            return {
                "section_title": next_section.get("section_title"),
                "section_description": next_section.get("section_description"),
                "step_count": len(active_steps),
                "estimated_duration": sum(
                    step.get("estimated_duration_minutes", 0)
                    for step in active_steps
                )
            }
        return None

    @staticmethod
    async def _update_session_identifier(
        session_id: UUID,
        new_identifier: str,
        db: AsyncSession
    ):
        """Update session to new step identifier.

        Args:
            session_id: Session UUID
            new_identifier: New step identifier string
            db: Database session
        """
        update_query = update(GuideSessionModel).where(
            GuideSessionModel.session_id == session_id
        ).values(
            current_step_identifier=new_identifier,
            updated_at=func.now()
        )
        await db.execute(update_query)
        await db.commit()

    @staticmethod
    async def _log_step_completion(
        session_id: UUID,
        step_identifier: str,
        completion_notes: Optional[str],
        db: AsyncSession
    ):
        """Log step completion event for analytics.

        Args:
            session_id: Session UUID
            step_identifier: Completed step identifier
            completion_notes: Optional notes about completion
            db: Database session
        """
        # This would integrate with a completion events table
        # For now, just pass - could be implemented later
        pass
