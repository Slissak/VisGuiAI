"""API routes for step management."""

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from shared.schemas.api_responses import StepCompletionRequest, StepResponse

from ..core.database import get_db
from ..services.step_service import (
    StepService, get_step_service, StepNotFoundError, InvalidStepStateError
)
from ..services.session_service import SessionService, get_session_service
from ..auth.middleware import get_current_user

router = APIRouter(prefix="/api/v1/steps", tags=["steps"])


@router.post(
    "/{step_id}/complete",
    response_model=StepResponse,
    responses={
        200: {
            "description": "Step completed successfully",
            "content": {
                "application/json": {
                    "example": {
                        "step_id": "750e8400-e29b-41d4-a716-446655440000",
                        "session_id": "550e8400-e29b-41d4-a716-446655440000",
                        "step_index": 3,
                        "title": "Configure deployment settings",
                        "status": "completed",
                        "completed_at": "2025-10-26T10:30:00Z",
                        "completion_method": "manual",
                        "time_taken_minutes": 5
                    }
                }
            }
        },
        404: {"description": "Step or session not found"},
        403: {"description": "Access denied to this session"},
        400: {"description": "Invalid step state or completion request"}
    },
    summary="Complete a step manually or via desktop monitoring"
)
async def complete_step(
    step_id: uuid.UUID,
    session_id: uuid.UUID,
    request: StepCompletionRequest,
    current_user: str = Depends(get_current_user),
    step_service: StepService = Depends(get_step_service),
    session_service: SessionService = Depends(get_session_service),
    db: AsyncSession = Depends(get_db)
):
    """
    Complete a step using either manual confirmation or desktop monitoring.

    This endpoint supports two completion methods:
    - **Manual**: User explicitly marks the step as complete
    - **Desktop Monitoring**: Automated verification via desktop agent (future feature)

    ## Example Request

    ```json
    {
      "completion_method": "manual",
      "completion_notes": "Settings configured successfully",
      "encountered_issues": null,
      "time_taken_minutes": 5
    }
    ```

    ## Example Response

    ```json
    {
      "step_id": "750e8400-e29b-41d4-a716-446655440000",
      "session_id": "550e8400-e29b-41d4-a716-446655440000",
      "step_index": 3,
      "title": "Configure deployment settings",
      "status": "completed",
      "completed_at": "2025-10-26T10:30:00Z",
      "completion_method": "manual",
      "time_taken_minutes": 5
    }
    ```

    ## Error Responses

    - **404**: Step or session not found
    - **403**: User doesn't own this session
    - **400**: Step already completed or invalid state
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

        response = await step_service.complete_step(session_id, step_id, request, db)
        return response

    except StepNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except InvalidStepStateError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
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
            detail=f"Failed to complete step: {str(e)}"
        )


@router.patch(
    "/{step_id}/assistance",
    response_model=StepResponse,
    responses={
        200: {
            "description": "Step assistance status updated",
            "content": {
                "application/json": {
                    "example": {
                        "step_id": "750e8400-e29b-41d4-a716-446655440000",
                        "session_id": "550e8400-e29b-41d4-a716-446655440000",
                        "step_index": 3,
                        "title": "Configure deployment settings",
                        "status": "in_progress",
                        "needs_assistance": True,
                        "assistance_requested_at": "2025-10-26T10:30:00Z"
                    }
                }
            }
        },
        404: {"description": "Step or session not found"},
        403: {"description": "Access denied to this session"}
    },
    summary="Mark a step as needing assistance"
)
async def mark_needs_assistance(
    step_id: uuid.UUID,
    session_id: uuid.UUID,
    needs_assistance: bool,
    current_user: str = Depends(get_current_user),
    step_service: StepService = Depends(get_step_service),
    session_service: SessionService = Depends(get_session_service),
    db: AsyncSession = Depends(get_db)
):
    """
    Mark a step as needing or not needing assistance.

    When users get stuck on a step, they can flag it for assistance.
    This helps identify difficult steps and can trigger help workflows.

    ## Example Request

    ```
    PATCH /api/v1/steps/{step_id}/assistance?session_id={session_id}&needs_assistance=true
    ```

    ## Example Response

    ```json
    {
      "step_id": "750e8400-e29b-41d4-a716-446655440000",
      "session_id": "550e8400-e29b-41d4-a716-446655440000",
      "step_index": 3,
      "title": "Configure deployment settings",
      "status": "in_progress",
      "needs_assistance": true,
      "assistance_requested_at": "2025-10-26T10:30:00Z"
    }
    ```

    ## Use Cases

    - User is stuck and needs help
    - Analytics: Identifying difficult steps
    - Triggering help workflows (future feature)
    - Tracking user experience issues
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

        response = await step_service.mark_needs_assistance(
            step_id, session_id, needs_assistance, db
        )
        return response

    except StepNotFoundError as e:
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
            detail=f"Failed to update step assistance: {str(e)}"
        )


@router.get(
    "/session/{session_id}",
    response_model=List[StepResponse],
    responses={
        200: {
            "description": "Session steps retrieved successfully",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "step_id": "750e8400-e29b-41d4-a716-446655440000",
                            "session_id": "550e8400-e29b-41d4-a716-446655440000",
                            "step_index": 0,
                            "title": "Install Vercel CLI",
                            "status": "completed",
                            "completed_at": "2025-10-26T09:15:00Z"
                        },
                        {
                            "step_id": "751e8400-e29b-41d4-a716-446655440000",
                            "session_id": "550e8400-e29b-41d4-a716-446655440000",
                            "step_index": 1,
                            "title": "Configure Vercel project",
                            "status": "in_progress",
                            "needs_assistance": False
                        },
                        {
                            "step_id": "752e8400-e29b-41d4-a716-446655440000",
                            "session_id": "550e8400-e29b-41d4-a716-446655440000",
                            "step_index": 2,
                            "title": "Deploy to production",
                            "status": "pending"
                        }
                    ]
                }
            }
        },
        404: {"description": "Session not found"},
        403: {"description": "Access denied to this session"}
    },
    summary="Get all steps for a session with completion status"
)
async def get_session_steps(
    session_id: uuid.UUID,
    current_user: str = Depends(get_current_user),
    step_service: StepService = Depends(get_step_service),
    session_service: SessionService = Depends(get_session_service),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all steps for a session with their completion status.

    Returns a list of all steps in the guide with their current status.
    Note: This violates progressive disclosure and should only be used
    for administrative or analytics purposes.

    ## Example Response

    ```json
    [
      {
        "step_id": "750e8400-e29b-41d4-a716-446655440000",
        "session_id": "550e8400-e29b-41d4-a716-446655440000",
        "step_index": 0,
        "title": "Install Vercel CLI",
        "status": "completed",
        "completed_at": "2025-10-26T09:15:00Z"
      },
      {
        "step_id": "751e8400-e29b-41d4-a716-446655440000",
        "session_id": "550e8400-e29b-41d4-a716-446655440000",
        "step_index": 1,
        "title": "Configure Vercel project",
        "status": "in_progress",
        "needs_assistance": false
      }
    ]
    ```

    ## Status Values

    - **completed**: Step has been completed
    - **in_progress**: Currently active step
    - **pending**: Not yet started
    - **blocked**: Cannot be completed (alternative steps generated)
    - **skipped**: User chose to skip this step
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

        steps = await step_service.get_session_steps(session_id, db)
        return steps

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get session steps: {str(e)}"
        )