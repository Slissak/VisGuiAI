"""Guide generation service with prompt templates and validation."""

import uuid
from datetime import datetime
from typing import Any

from shared.schemas.api_responses import GuideGenerationRequest, GuideGenerationResponse
from shared.schemas.llm_request import LLMProvider
from shared.schemas.step import Step
from shared.schemas.step_guide import DifficultyLevel, StepGuide
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..core.cache import CacheManager
from ..exceptions import ValidationError
from ..models.database import (
    LLMGenerationRequestModel,
    SectionModel,
    StepGuideModel,
    StepModel,
    StepStatus,
)
from ..utils.logging import get_logger
from .llm_service import LLMService

logger = get_logger(__name__)


class GuideValidationError(ValidationError):
    """Exception raised when guide validation fails."""

    def __init__(self, reason: str):
        super().__init__(field="guide_data", value="<guide_content>", reason=reason)


class GuideService:
    """Service for generating and managing step-by-step guides."""

    def __init__(self, llm_service: LLMService, cache: CacheManager = None):
        self.llm_service = llm_service
        self.cache = cache

    async def generate_guide(
        self, request: GuideGenerationRequest, db: AsyncSession
    ) -> GuideGenerationResponse:
        """Generate a new step-by-step guide."""

        logger.info(
            "guide_generation_started",
            user_query=request.user_query,
            difficulty=request.difficulty_preference.value,
            format_preference=request.format_preference,
        )

        # Generate guide using LLM service
        guide_data, provider_used, generation_time = (
            await self.llm_service.generate_guide(
                user_query=request.user_query,
                difficulty=request.difficulty_preference.value,
                format_preference=request.format_preference,
            )
        )

        # Extract raw LLM response for debugging
        raw_llm_response = guide_data.get("_raw_llm_response", None)

        # Validate the generated guide
        validated_data = await self._validate_and_process_guide(guide_data)
        validated_data["raw_llm_response"] = raw_llm_response

        # Save to database
        guide_id = await self._save_guide_to_database(
            validated_data, request.difficulty_preference, db
        )

        # Record LLM generation request
        await self._record_llm_request(
            request=request,
            guide_id=guide_id,
            provider_used=provider_used,
            generation_time=generation_time,
            db=db,
        )

        # Map provider names to enum values
        provider_mapping = {
            "openai": LLMProvider.OPENAI,
            "anthropic": LLMProvider.ANTHROPIC,
            "lm_studio": LLMProvider.LM_STUDIO,
            "mock": LLMProvider.OPENAI,  # Default for mock
        }

        logger.info(
            "guide_generation_completed",
            guide_id=str(guide_id),
            total_steps=validated_data["total_steps"],
            total_sections=validated_data["total_sections"],
            provider=provider_used,
            generation_time=generation_time,
        )

        # Create response with guide info
        guide_info = validated_data["guide_info"]
        return GuideGenerationResponse(
            guide_id=guide_id,
            guide=StepGuide(
                guide_id=guide_id,
                title=guide_info["title"],
                description=guide_info["description"],
                total_steps=validated_data["total_steps"],
                estimated_duration_minutes=validated_data["estimated_duration_minutes"],
                difficulty_level=request.difficulty_preference,
                category=guide_info.get("category", "general"),
                llm_prompt_template="v1.0",
                generation_metadata={
                    "source": "llm_generated",
                    "provider": provider_used,
                },
                created_at=datetime.utcnow(),
                steps=[],  # Steps are stored in database, not returned in initial response
            ),
            generation_time_seconds=generation_time,
            llm_provider=provider_mapping.get(provider_used, LLMProvider.OPENAI),
        )

    async def get_guide(
        self, guide_id: uuid.UUID, db: AsyncSession
    ) -> StepGuide | None:
        """Retrieve a guide by ID with caching."""
        # Try to get from cache first (TTL: 1 hour)
        if self.cache:
            cache_key = self.cache.make_guide_key(str(guide_id))
            cached_guide = await self.cache.get(cache_key)

            if cached_guide:
                logger.debug("guide_cache_hit", guide_id=str(guide_id))
                # Reconstruct StepGuide from cached data
                return StepGuide(**cached_guide)

        # Cache miss - fetch from database
        logger.debug("guide_cache_miss", guide_id=str(guide_id))

        # Optimization: Use selectinload to avoid N+1 queries for steps and sections
        query = (
            select(StepGuideModel)
            .options(
                selectinload(StepGuideModel.steps),
                selectinload(StepGuideModel.sections),
            )
            .where(StepGuideModel.guide_id == guide_id)
        )
        result = await db.execute(query)
        guide_model = result.scalar_one_or_none()

        if not guide_model:
            return None

        # Steps are already loaded via selectinload
        step_models = sorted(guide_model.steps, key=lambda x: x.step_index)

        # Convert to Pydantic models
        steps = [
            Step(
                step_id=step.step_id,
                guide_id=step.guide_id,
                step_index=step.step_index,
                title=step.title,
                description=step.description,
                completion_criteria=step.completion_criteria,
                assistance_hints=step.assistance_hints,
                estimated_duration_minutes=step.estimated_duration_minutes,
                requires_desktop_monitoring=step.requires_desktop_monitoring,
                visual_markers=step.visual_markers,
                dependencies=step.dependencies,
                completed=False,
                needs_assistance=False,
            )
            for step in step_models
        ]

        guide = StepGuide(
            guide_id=guide_model.guide_id,
            title=guide_model.title,
            description=guide_model.description,
            total_steps=guide_model.total_steps,
            estimated_duration_minutes=guide_model.estimated_duration_minutes,
            difficulty_level=guide_model.difficulty_level,
            category=guide_model.category,
            llm_prompt_template=guide_model.llm_prompt_template,
            generation_metadata=guide_model.generation_metadata,
            created_at=guide_model.created_at,
            steps=steps,
        )

        # Cache the guide data (TTL: 1 hour)
        if self.cache:
            cache_key = self.cache.make_guide_key(str(guide_id))
            await self.cache.set(
                cache_key, guide.model_dump(), ttl=self.cache.TTL_GUIDE_DATA
            )

        return guide

    async def _validate_and_process_guide(
        self, guide_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Validate and process LLM-generated guide data.

        Returns a dictionary with guide info and sections for database storage.
        """
        try:
            guide_info = guide_data["guide"]

            # Preserve raw LLM response if present
            if "_raw_llm_response" in guide_data:
                guide_info["_raw_llm_response"] = guide_data["_raw_llm_response"]

            # Generate guide ID
            guide_id = uuid.uuid4()

            # Check if guide has sections structure (new format) or flat steps (old format)
            sections = guide_info.get("sections", [])

            # If no sections, create a default section from flat steps list
            if not sections and "steps" in guide_info:
                sections = [
                    {
                        "section_id": "main",
                        "section_title": "Steps",
                        "section_description": "Main steps for this guide",
                        "section_order": 0,
                        "steps": guide_info["steps"],
                    }
                ]

            # Count total steps across all sections
            total_steps = sum(len(section.get("steps", [])) for section in sections)

            # Calculate total estimated duration
            total_duration = 0
            for section in sections:
                for step in section.get("steps", []):
                    total_duration += step.get("estimated_duration_minutes", 5)

            # Return structured data for database storage
            return {
                "guide_id": guide_id,
                "guide_info": guide_info,
                "sections": sections,
                "total_steps": total_steps,
                "total_sections": len(sections),
                "estimated_duration_minutes": guide_info.get(
                    "estimated_duration_minutes", total_duration
                ),
            }

        except Exception as e:
            raise GuideValidationError(f"Failed to validate guide: {e}") from e

    async def _save_guide_to_database(
        self,
        validated_data: dict[str, Any],
        difficulty_level: DifficultyLevel,
        db: AsyncSession,
    ) -> uuid.UUID:
        """Save validated guide with sections to database."""
        guide_id = validated_data["guide_id"]
        guide_info = validated_data["guide_info"]
        sections = validated_data["sections"]

        # CRITICAL FIX: Renumber step_index to be globally unique
        # LLMs often generate per-section step_index (1, 2, 1, 2, 1) which causes duplicates
        # IMPORTANT: Start at 0 for zero-based indexing
        # ALSO: Add step_identifier to guide_data JSON for adaptation support
        global_step_counter = 0
        for section in guide_info.get("sections", []):
            for step in section.get("steps", []):
                step["step_index"] = global_step_counter
                step["step_identifier"] = str(
                    global_step_counter
                )  # Add identifier for adaptation
                global_step_counter += 1

        # Create guide model with guide_data JSON
        guide_model = StepGuideModel(
            guide_id=guide_id,
            title=guide_info["title"],
            description=guide_info["description"],
            total_steps=validated_data["total_steps"],
            total_sections=validated_data["total_sections"],
            estimated_duration_minutes=validated_data["estimated_duration_minutes"],
            difficulty_level=str(difficulty_level.value),
            category=guide_info.get("category", "general"),
            llm_prompt_template="v1.0",
            generation_metadata={"source": "llm_generated"},
            guide_data=guide_info,  # Store full JSON structure including sections (now with fixed step_index)
        )

        db.add(guide_model)

        # Invalidate cache for this guide (in case it's being regenerated)
        if self.cache:
            cache_key = self.cache.make_guide_key(str(guide_id))
            await self.cache.delete(cache_key)

        # Create section and step models
        global_step_index = 0
        for section_data in sections:
            section_model = SectionModel(
                section_id=uuid.uuid4(),
                guide_id=guide_id,
                section_identifier=section_data["section_id"],
                section_title=section_data["section_title"],
                section_description=section_data["section_description"],
                section_order=section_data["section_order"],
                estimated_duration_minutes=sum(
                    step.get("estimated_duration_minutes", 5)
                    for step in section_data.get("steps", [])
                ),
            )
            db.add(section_model)

            # Create step models for this section
            for step_data in section_data.get("steps", []):
                step_identifier = str(step_data.get("step_index", global_step_index))
                step_model = StepModel(
                    step_id=uuid.uuid4(),
                    guide_id=guide_id,
                    section_id=section_model.section_id,
                    step_index=global_step_index,
                    step_identifier=step_identifier,
                    step_status=StepStatus.ACTIVE,
                    title=step_data["title"],
                    description=step_data["description"],
                    completion_criteria=step_data["completion_criteria"],
                    assistance_hints=step_data.get("assistance_hints", []),
                    estimated_duration_minutes=step_data.get(
                        "estimated_duration_minutes", 5
                    ),
                    requires_desktop_monitoring=step_data.get(
                        "requires_desktop_monitoring", False
                    ),
                    visual_markers=step_data.get("visual_markers", []),
                    prerequisites=step_data.get("prerequisites", []),
                    dependencies=[],
                )
                db.add(step_model)
                global_step_index += 1

        await db.commit()
        return guide_id

    async def _record_llm_request(
        self,
        request: GuideGenerationRequest,
        guide_id: uuid.UUID,
        provider_used: str,
        generation_time: float,
        db: AsyncSession,
    ):
        """Record LLM generation request for audit purposes."""
        # Map provider names to enum values
        provider_mapping = {
            "openai": LLMProvider.OPENAI,
            "anthropic": LLMProvider.ANTHROPIC,
            "lm_studio": LLMProvider.LM_STUDIO,
            "mock": LLMProvider.OPENAI,  # Default for mock
        }

        llm_request = LLMGenerationRequestModel(
            request_id=uuid.uuid4(),
            user_query=request.user_query,
            llm_provider=provider_mapping.get(provider_used, LLMProvider.OPENAI),
            prompt_template_version="v1.0",
            generated_guide_id=guide_id,
            generation_time_seconds=generation_time,
            token_usage={
                "provider": provider_used
            },  # Could be expanded with actual token usage
        )

        db.add(llm_request)
        await db.commit()


async def get_guide_service(llm_service: LLMService) -> GuideService:
    """Dependency to get guide service."""
    from ..core.cache import cache_manager

    return GuideService(llm_service, cache=cache_manager)
