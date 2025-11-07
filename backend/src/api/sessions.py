"""API routes for session management."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from shared.schemas.api_responses import (
    SessionCreateRequest,
    SessionDetailResponse,
    SessionResponse,
    SessionUpdateRequest,
)
from shared.schemas.guide_session import SessionStatus
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.middleware import get_current_user
from ..core.database import get_db
from ..core.redis import get_session_store
from ..services.guide_service import GuideService
from ..services.llm_service import get_llm_service
from ..services.session_service import (
    InvalidSessionStateError,
    SessionNotFoundError,
    SessionService,
    get_session_service,
)

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


@router.post("/", response_model=SessionResponse)
async def create_session(
    request: SessionCreateRequest,
    current_user: str = Depends(get_current_user),
    llm_service=Depends(get_llm_service),
    session_store=Depends(get_session_store),
    db: AsyncSession = Depends(get_db),
):
    """Create a new guide session."""
    # Ensure the user_id in request matches authenticated user
    if request.user_id != current_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot create session for another user",
        )

    try:
        guide_service = GuideService(llm_service)
        session_service = SessionService(guide_service, session_store)
        response = await session_service.create_session(request, db)
        return response
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create session: {str(e)}",
        )


@router.get(
    "/{session_id}",
    response_model=SessionDetailResponse,
    response_model_exclude_none=True,
)
async def get_session(
    session_id: uuid.UUID,
    current_user: str = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_service),
    db: AsyncSession = Depends(get_db),
):
    """Get detailed session information."""
    session_detail = await session_service.get_session(session_id, db)

    if not session_detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )

    # Verify user owns this session
    if session_detail.session.user_id != current_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this session",
        )

    return session_detail


@router.patch("/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: uuid.UUID,
    request: SessionUpdateRequest,
    current_user: str = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_service),
    db: AsyncSession = Depends(get_db),
):
    """Update session status."""
    try:
        # First verify user owns this session
        session_detail = await session_service.get_session(session_id, db)
        if not session_detail:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found",
            )

        if session_detail.session.user_id != current_user:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this session",
            )

        response = await session_service.update_session(session_id, request, db)
        return response

    except SessionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except InvalidSessionStateError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update session: {str(e)}",
        )


@router.get("/user/{user_id}", response_model=list[SessionResponse])
async def get_user_sessions(
    user_id: str,
    status: SessionStatus | None = None,
    current_user: str = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_service),
    db: AsyncSession = Depends(get_db),
):
    """Get user's sessions, optionally filtered by status."""
    # Verify user can only access their own sessions
    if user_id != current_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access another user's sessions",
        )

    try:
        sessions = await session_service.get_user_sessions(user_id, status, db)
        return sessions
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user sessions: {str(e)}",
        )


@router.post("/{session_id}/advance", response_model=dict)
async def advance_to_next_step(
    session_id: uuid.UUID,
    current_user: str = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_service),
    db: AsyncSession = Depends(get_db),
):
    """Advance session to the next step."""
    try:
        # First verify user owns this session
        session_detail = await session_service.get_session(session_id, db)
        if not session_detail:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found",
            )

        if session_detail.session.user_id != current_user:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this session",
            )

        has_next_step = await session_service.advance_to_next_step(session_id, db)

        return {
            "advanced": has_next_step,
            "message": (
                "Advanced to next step" if has_next_step else "Session completed"
            ),
        }

    except SessionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to advance session: {str(e)}",
        )
