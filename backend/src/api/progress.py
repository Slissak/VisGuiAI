"""API routes for progress tracking."""

import uuid
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from shared.schemas.api_responses import ProgressResponse
from shared.schemas.progress_tracker import ProgressUpdate

from ..core.database import get_db
from ..services.progress_service import (
    ProgressService, get_progress_service, ProgressNotFoundError
)
from ..services.session_service import SessionService, get_session_service
from ..auth.middleware import get_current_user

router = APIRouter(prefix="/api/v1/progress", tags=["progress"])


@router.get(
    "/{session_id}",
    response_model=ProgressResponse,
    responses={
        200: {
            "description": "Progress information retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "session_id": "550e8400-e29b-41d4-a716-446655440000",
                        "total_steps": 12,
                        "completed_steps": 5,
                        "current_step_index": 5,
                        "completion_percentage": 41.67,
                        "estimated_time_remaining_minutes": 35,
                        "time_elapsed_minutes": 25,
                        "last_updated": "2025-10-26T10:30:00Z"
                    }
                }
            }
        },
        404: {"description": "Session or progress not found"},
        403: {"description": "Access denied to this session"}
    },
    summary="Get current progress for a guide session"
)
async def get_progress(
    session_id: uuid.UUID,
    current_user: str = Depends(get_current_user),
    progress_service: ProgressService = Depends(get_progress_service),
    session_service: SessionService = Depends(get_session_service),
    db: AsyncSession = Depends(get_db)
):
    """
    Get current progress information for a guide session.

    Returns comprehensive progress tracking including completion percentage,
    time estimates, and step counts.

    ## Example Response

    ```json
    {
      "session_id": "550e8400-e29b-41d4-a716-446655440000",
      "total_steps": 12,
      "completed_steps": 5,
      "current_step_index": 5,
      "completion_percentage": 41.67,
      "estimated_time_remaining_minutes": 35,
      "time_elapsed_minutes": 25,
      "last_updated": "2025-10-26T10:30:00Z"
    }
    ```

    ## Fields

    - **total_steps**: Total number of steps in the guide
    - **completed_steps**: Number of steps completed so far
    - **current_step_index**: Index of the current step
    - **completion_percentage**: Progress as a percentage (0-100)
    - **estimated_time_remaining_minutes**: Estimated time to complete remaining steps
    - **time_elapsed_minutes**: Total time spent so far
    """
    try:
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

        progress = await progress_service.get_progress(session_id, db)

        if not progress:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Progress tracker for session {session_id} not found"
            )

        return progress

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get progress: {str(e)}"
        )


@router.patch(
    "/{session_id}",
    response_model=ProgressResponse,
    responses={
        200: {
            "description": "Progress updated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "session_id": "550e8400-e29b-41d4-a716-446655440000",
                        "total_steps": 12,
                        "completed_steps": 6,
                        "current_step_index": 6,
                        "completion_percentage": 50.0,
                        "estimated_time_remaining_minutes": 30
                    }
                }
            }
        },
        404: {"description": "Session or progress not found"},
        403: {"description": "Access denied to this session"},
        400: {"description": "Invalid update data"}
    },
    summary="Update progress tracker with new data"
)
async def update_progress(
    session_id: uuid.UUID,
    update: ProgressUpdate,
    current_user: str = Depends(get_current_user),
    progress_service: ProgressService = Depends(get_progress_service),
    session_service: SessionService = Depends(get_session_service),
    db: AsyncSession = Depends(get_db)
):
    """
    Update progress tracker with new completion data.

    This endpoint is typically called internally when steps are completed,
    but can also be used to manually update progress information.

    ## Example Request

    ```json
    {
      "completed_steps": 6,
      "current_step_index": 6,
      "time_elapsed_minutes": 30
    }
    ```

    ## Example Response

    ```json
    {
      "session_id": "550e8400-e29b-41d4-a716-446655440000",
      "total_steps": 12,
      "completed_steps": 6,
      "completion_percentage": 50.0,
      "estimated_time_remaining_minutes": 30
    }
    ```
    """
    try:
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

        progress = await progress_service.update_progress(session_id, update, db)
        return progress

    except ProgressNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update progress: {str(e)}"
        )


@router.get(
    "/{session_id}/estimates",
    response_model=Dict[str, float],
    responses={
        200: {
            "description": "Time estimates calculated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "estimated_total_minutes": 60,
                        "estimated_remaining_minutes": 35,
                        "average_step_duration_minutes": 5.2,
                        "time_elapsed_minutes": 25
                    }
                }
            }
        },
        404: {"description": "Session or progress not found"},
        403: {"description": "Access denied to this session"}
    },
    summary="Get time estimates based on actual completion times"
)
async def get_time_estimates(
    session_id: uuid.UUID,
    current_user: str = Depends(get_current_user),
    progress_service: ProgressService = Depends(get_progress_service),
    session_service: SessionService = Depends(get_session_service),
    db: AsyncSession = Depends(get_db)
):
    """
    Calculate updated time estimates based on actual completion times.

    This endpoint analyzes the user's actual completion times for steps
    and provides more accurate estimates for remaining time.

    ## Example Response

    ```json
    {
      "estimated_total_minutes": 60,
      "estimated_remaining_minutes": 35,
      "average_step_duration_minutes": 5.2,
      "time_elapsed_minutes": 25
    }
    ```

    ## Fields

    - **estimated_total_minutes**: Total estimated time for the entire guide
    - **estimated_remaining_minutes**: Estimated time to complete remaining steps
    - **average_step_duration_minutes**: User's average time per step
    - **time_elapsed_minutes**: Total time spent so far
    """
    try:
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

        estimates = await progress_service.calculate_time_estimates(session_id, db)
        return estimates

    except ProgressNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to calculate time estimates: {str(e)}"
        )


@router.get(
    "/{session_id}/analytics",
    response_model=Dict[str, Any],
    responses={
        200: {
            "description": "Session analytics retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "session_id": "550e8400-e29b-41d4-a716-446655440000",
                        "total_steps": 12,
                        "completed_steps": 5,
                        "steps_needing_assistance": 1,
                        "average_completion_time_minutes": 5.2,
                        "fastest_step_minutes": 2,
                        "slowest_step_minutes": 12,
                        "completion_rate": 0.42,
                        "started_at": "2025-10-26T09:00:00Z",
                        "last_activity_at": "2025-10-26T10:30:00Z"
                    }
                }
            }
        },
        404: {"description": "Session or progress not found"},
        403: {"description": "Access denied to this session"}
    },
    summary="Get detailed analytics for a session"
)
async def get_session_analytics(
    session_id: uuid.UUID,
    current_user: str = Depends(get_current_user),
    progress_service: ProgressService = Depends(get_progress_service),
    session_service: SessionService = Depends(get_session_service),
    db: AsyncSession = Depends(get_db)
):
    """
    Get detailed analytics and insights for a guide session.

    Provides comprehensive analytics including completion metrics,
    time statistics, and user behavior patterns.

    ## Example Response

    ```json
    {
      "session_id": "550e8400-e29b-41d4-a716-446655440000",
      "total_steps": 12,
      "completed_steps": 5,
      "steps_needing_assistance": 1,
      "average_completion_time_minutes": 5.2,
      "fastest_step_minutes": 2,
      "slowest_step_minutes": 12,
      "completion_rate": 0.42,
      "started_at": "2025-10-26T09:00:00Z",
      "last_activity_at": "2025-10-26T10:30:00Z"
    }
    ```

    ## Use Cases

    - Understanding user behavior patterns
    - Identifying difficult steps (high assistance rate)
    - Optimizing guide structure based on completion times
    - Tracking user engagement and session duration
    """
    try:
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

        analytics = await progress_service.get_session_analytics(session_id, db)
        return analytics

    except ProgressNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get session analytics: {str(e)}"
        )