"""API routes for guide management."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from shared.schemas.api_responses import (
    GuideDetailResponse,
    GuideGenerationRequest,
    GuideGenerationResponse,
)
from shared.schemas.step_guide import DifficultyLevel
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.middleware import get_current_user
from ..core.database import get_db
from ..services.guide_service import GuideService
from ..services.llm_service import get_llm_service

router = APIRouter(prefix="/api/v1/guides", tags=["guides"])


@router.post(
    "/generate",
    response_model=GuideGenerationResponse,
    response_model_exclude_none=True,
)
async def generate_guide(
    request: GuideGenerationRequest,
    current_user: str = Depends(get_current_user),
    llm_service=Depends(get_llm_service),
    db: AsyncSession = Depends(get_db),
):
    """Generate a new step-by-step guide using LLM."""
    try:
        guide_service = GuideService(llm_service)
        response = await guide_service.generate_guide(request, db)
        return response
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate guide: {str(e)}",
        ) from e


@router.get(
    "/{guide_id}", response_model=GuideDetailResponse, response_model_exclude_none=True
)
async def get_guide(
    guide_id: uuid.UUID,
    current_user: str = Depends(get_current_user),
    llm_service=Depends(get_llm_service),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific guide by ID."""
    guide_service = GuideService(llm_service)
    guide = await guide_service.get_guide(guide_id, db)

    if not guide:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Guide {guide_id} not found"
        )

    return GuideDetailResponse(guide=guide)


@router.get(
    "/", response_model=list[GuideDetailResponse], response_model_exclude_none=True
)
async def list_guides(
    difficulty: DifficultyLevel | None = None,
    category: str | None = None,
    limit: int = 20,
    offset: int = 0,
    current_user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List guides with optional filtering."""
    # This is a placeholder - would need to implement in GuideService
    # For now, return empty list
    return []
