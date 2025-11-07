"""API routes for instruction-based guide generation and progressive step management."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from shared.schemas.step_guide import DifficultyLevel
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.middleware import get_current_user
from ..core.config import get_settings
from ..core.database import get_db
from ..models.user import UserModel
from ..services.guide_service import GuideService
from ..services.llm_service import get_llm_service
from ..services.session_service import SessionService, get_session_service
from ..services.step_disclosure_service import StepDisclosureService
from ..shared.billing.cost_calculator import CostCalculator
from ..shared.usage.usage_service import UsageService

settings = get_settings()


router = APIRouter(prefix="/api/v1/instruction-guides", tags=["instruction-guides"])


# Helper function to get user tier budgets
def get_user_budgets(user_tier: str = "free") -> tuple[float, float]:
    """Get daily and monthly budget limits for a user tier.

    For now, uses placeholder values. In production, this would:
    1. Look up user's tier from database
    2. Convert token limits to cost estimates using pricing.yaml
    3. Return (daily_budget, monthly_budget) in USD
    """
    # Placeholder budgets (in USD)
    tier_budgets = {
        "free": (0.50, 5.00),          # $0.50/day, $5/month
        "basic": (2.50, 25.00),        # $2.50/day, $25/month
        "professional": (10.00, 100.00),  # $10/day, $100/month
        "enterprise": (50.00, 500.00),    # $50/day, $500/month
    }
    return tier_budgets.get(user_tier, tier_budgets["free"])


# Request/Response Models
class InstructionGuideRequest(BaseModel):
    """Request model for instruction-based guide generation."""
    instruction: str = Field(
        ...,
        min_length=5,
        max_length=1000,
        description="User instruction for the guide (5-1000 characters)"
    )
    difficulty: DifficultyLevel = Field(default=DifficultyLevel.BEGINNER, description="Guide difficulty level")
    format_preference: str = Field(default="detailed", description="Format preference for the guide")


class StepCompletionRequest(BaseModel):
    """Request model for marking step as completed."""
    completion_notes: str | None = Field(None, description="Optional notes about step completion")
    encountered_issues: str | None = Field(None, description="Any issues encountered during step")
    time_taken_minutes: int | None = Field(None, description="Actual time taken for step")


class CurrentStepResponse(BaseModel):
    """Response model for current step information."""
    session_id: str
    status: str
    guide_title: str
    guide_description: str
    current_section: dict
    current_step: dict
    progress: dict
    navigation: dict


class InstructionGuideGenerationResponse(BaseModel):
    """Response model for instruction-based guide generation."""
    session_id: str
    guide_id: str
    guide_title: str
    message: str
    first_step: dict


@router.post(
    "/generate",
    response_model=InstructionGuideGenerationResponse,
    response_model_exclude_none=True,
    status_code=201,
    responses={
        201: {
            "description": "Guide generated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "session_id": "550e8400-e29b-41d4-a716-446655440000",
                        "guide_id": "650e8400-e29b-41d4-a716-446655440000",
                        "guide_title": "How to deploy React app to Vercel",
                        "message": "Guide generated successfully. Start with the first step below.",
                        "first_step": {
                            "session_id": "550e8400-e29b-41d4-a716-446655440000",
                            "status": "active",
                            "current_step": {
                                "step_identifier": "0",
                                "title": "Install Vercel CLI",
                                "description": "Install the Vercel CLI tool to enable command-line deployments",
                                "completion_criteria": "Vercel CLI is installed and accessible from terminal",
                                "assistance_hints": ["Use npm install -g vercel", "Verify installation with 'vercel --version'"],
                                "estimated_duration_minutes": 5
                            },
                            "progress": {
                                "total_steps": 12,
                                "completed_steps": 0,
                                "completion_percentage": 0
                            }
                        }
                    }
                }
            }
        },
        400: {
            "description": "Invalid request parameters",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "instruction field is required"
                    }
                }
            }
        },
        500: {
            "description": "LLM generation failed",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Failed to generate instruction guide: All LLM providers unavailable"
                    }
                }
            }
        }
    },
    summary="Generate step-by-step guide from natural language instruction"
)
async def generate_instruction_guide(
    request: InstructionGuideRequest,
    current_user: UserModel = Depends(get_current_user),
    llm_service = Depends(get_llm_service),
    session_service: SessionService = Depends(get_session_service),
    db: AsyncSession = Depends(get_db)
):
    """
    Generate a step-by-step guide from natural language instruction.

    This endpoint uses an LLM to convert natural language instructions into structured,
    actionable step-by-step guides. The guide uses progressive disclosure - only the
    first step is returned to avoid overwhelming users.

    ## How It Works

    1. Takes a user's natural language instruction (e.g., "deploy a React app to Vercel")
    2. Uses LLM to generate a structured guide with logical sections
    3. Creates a new session for tracking progress through the guide
    4. Returns only the first step with progress information

    ## Guide Structure

    The generated guide includes:
    - Logical sections (Setup, Configuration, Execution, Verification, etc.)
    - Multiple steps per section with clear titles and descriptions
    - Completion criteria for each step
    - Helpful hints and visual markers (if applicable)
    - Time estimates per step

    ## Progressive Disclosure

    Only the current step is revealed to prevent user overwhelm. Users advance through
    steps one at a time using the `/complete-step` endpoint.

    ## Example Request

    ```json
    {
      "instruction": "deploy a React app to Vercel",
      "difficulty": "beginner",
      "format_preference": "detailed"
    }
    ```

    ## Example Response

    ```json
    {
      "session_id": "550e8400-e29b-41d4-a716-446655440000",
      "guide_id": "650e8400-e29b-41d4-a716-446655440000",
      "guide_title": "How to deploy React app to Vercel",
      "message": "Guide generated successfully. Start with the first step below.",
      "first_step": {
        "status": "active",
        "current_step": {
          "step_identifier": "0",
          "title": "Install Vercel CLI",
          "description": "Install the Vercel CLI tool...",
          "completion_criteria": "Vercel CLI is installed...",
          "assistance_hints": ["Use npm install -g vercel"],
          "estimated_duration_minutes": 5
        },
        "progress": {
          "total_steps": 12,
          "completed_steps": 0,
          "completion_percentage": 0
        }
      }
    }
    ```

    ## Parameters

    - **instruction**: Natural language description of the task (required)
    - **difficulty**: User's skill level (beginner, intermediate, advanced)
    - **format_preference**: Level of detail desired (detailed, concise)

    ## Error Responses

    - **400**: Invalid request parameters (missing instruction, invalid difficulty)
    - **500**: LLM generation failed (all providers unavailable or generation error)
    """
    try:
        # 1. Check user quota before generating guide
        usage_service = UsageService(db)
        daily_budget, monthly_budget = get_user_budgets(current_user.tier)

        can_proceed, error_message = await usage_service.check_limits(
            user_id=current_user.user_id,
            daily_budget=daily_budget,
            monthly_budget=monthly_budget
        )

        if not can_proceed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Usage quota exceeded: {error_message}"
            )

        # 2. Generate guide using LLM service
        guide_service = GuideService(llm_service)

        # Create guide generation request in expected format
        from shared.schemas.api_responses import GuideGenerationRequest
        guide_request = GuideGenerationRequest(
            user_query=request.instruction,
            user_id=current_user.user_id,
            difficulty_preference=request.difficulty,
            format_preference=request.format_preference
        )

        # Generate the guide (this now stores raw_llm_response in validated_data)
        guide_response = await guide_service.generate_guide(guide_request, db)
        guide_id = guide_response.guide.guide_id

        # Create a new session for this guide
        session_response = await session_service.create_session_simple(
            guide_id=guide_id,
            user_id=current_user.user_id,
            db=db
        )
        session_id = session_response.session_id

        # Get the guide to access raw LLM response
        from sqlalchemy import select

        from ..models.database import StepGuideModel
        guide_query = select(StepGuideModel).where(StepGuideModel.guide_id == guide_id)
        guide_result = await db.execute(guide_query)
        guide_model = guide_result.scalar_one_or_none()
        raw_llm_response = guide_model.guide_data.get("_raw_llm_response") if guide_model else None

        # Get the first step only using step disclosure service
        first_step_data = await StepDisclosureService.get_current_step_only(
            session_id, db
        )

        # Add raw LLM response to first_step_data for debugging
        if raw_llm_response:
            first_step_data["_raw_llm_response"] = raw_llm_response

        # 3. Calculate cost and increment usage
        # TODO: Get actual token counts from LLM response
        # For now, use placeholder values: ~2000 tokens input, ~3000 tokens output
        # This should be replaced with actual token usage from the LLM service
        cost_calculator = CostCalculator()
        estimated_cost = cost_calculator.calculate_cost(
            model="claude-3-sonnet",  # TODO: Get actual model from llm_service
            prompt_tokens=2000,
            completion_tokens=3000
        )

        # Increment user usage with estimated cost
        await usage_service.increment_usage(
            user_id=current_user.user_id,
            cost=estimated_cost
        )

        return InstructionGuideGenerationResponse(
            session_id=str(session_id),
            guide_id=str(guide_id),
            guide_title=guide_response.guide.title,
            message="Guide generated successfully. Start with the first step below.",
            first_step=first_step_data
        )

    except Exception as e:
        import traceback
        error_details = f"Failed to generate instruction guide: {str(e)}\nTraceback: {traceback.format_exc()}"
        print(f"ERROR in generate_instruction_guide: {error_details}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_details if settings.debug else f"Failed to generate instruction guide: {str(e)}"
        )


@router.get("/{session_id}/current-step", response_model=CurrentStepResponse, response_model_exclude_none=True)
async def get_current_step(
    session_id: uuid.UUID,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    session_service: SessionService = Depends(get_session_service)
):
    """Get the current step for a guide session.

    Returns only the current step information to avoid overwhelming the user.
    Includes progress tracking and navigation options.
    """
    try:
        # Verify session belongs to current user
        session = await session_service.get_session_simple(session_id, db)

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found"
            )

        if session.user_id != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this session"
            )

        # Get current step using disclosure service
        current_step_data = await StepDisclosureService.get_current_step_only(
            session_id, db
        )

        return CurrentStepResponse(**current_step_data)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.post(
    "/{session_id}/complete-step",
    status_code=200,
    responses={
        200: {
            "description": "Step completed and advanced to next step",
            "content": {
                "application/json": {
                    "example": {
                        "session_id": "550e8400-e29b-41d4-a716-446655440000",
                        "status": "active",
                        "current_step": {
                            "step_identifier": "1",
                            "title": "Configure Vercel project",
                            "description": "Link your React app to Vercel project",
                            "completion_criteria": "Vercel project is configured",
                            "assistance_hints": ["Run 'vercel' in project directory"],
                            "estimated_duration_minutes": 10
                        },
                        "progress": {
                            "total_steps": 12,
                            "completed_steps": 1,
                            "completion_percentage": 8.33
                        }
                    }
                }
            }
        },
        404: {
            "description": "Session not found",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Session 550e8400-e29b-41d4-a716-446655440000 not found"
                    }
                }
            }
        },
        403: {
            "description": "Access denied to session",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Access denied to this session"
                    }
                }
            }
        }
    },
    summary="Complete current step and advance to next"
)
async def complete_current_step(
    session_id: uuid.UUID,
    request: StepCompletionRequest,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    session_service: SessionService = Depends(get_session_service)
):
    """
    Mark current step as completed and advance to the next step.

    This endpoint implements progressive disclosure by advancing the user through
    the guide one step at a time. When a step is completed, the next step is
    automatically revealed.

    ## How It Works

    1. Validates the user owns the session
    2. Marks the current step as completed with optional notes
    3. Records completion time if provided
    4. Advances to the next step in the guide
    5. Returns the new current step (or completion status if guide is finished)

    ## Example Request

    ```json
    {
      "completion_notes": "CLI installed successfully",
      "encountered_issues": null,
      "time_taken_minutes": 3
    }
    ```

    ## Example Response (Next Step)

    ```json
    {
      "session_id": "550e8400-e29b-41d4-a716-446655440000",
      "status": "active",
      "current_step": {
        "step_identifier": "1",
        "title": "Configure Vercel project",
        "description": "Link your React app to Vercel project...",
        "completion_criteria": "Vercel project is configured",
        "assistance_hints": ["Run 'vercel' in project directory"],
        "estimated_duration_minutes": 10
      },
      "progress": {
        "total_steps": 12,
        "completed_steps": 1,
        "completion_percentage": 8.33
      }
    }
    ```

    ## Example Response (Guide Completed)

    ```json
    {
      "status": "completed",
      "message": "Congratulations! You've completed the guide.",
      "total_steps": 12,
      "completed_steps": 12,
      "completion_percentage": 100
    }
    ```

    ## Parameters

    - **completion_notes**: Optional notes about step completion
    - **encountered_issues**: Any issues encountered during step
    - **time_taken_minutes**: Actual time taken to complete the step

    ## Error Responses

    - **404**: Session not found
    - **403**: User doesn't own this session
    - **500**: Failed to complete step
    """
    try:
        # Verify session belongs to current user
        session = await session_service.get_session_simple(session_id, db)
        print(f"complete_current_step: session: {session}")
        print(f"complete_current_step: current_user: {current_user}")

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found"
            )

        if session.user_id != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this session"
            )

        # Advance to next step using disclosure service
        next_step_data = await StepDisclosureService.advance_to_next_step(
            session_id=session_id,
            completion_notes=request.completion_notes,
            db=db
        )

        if next_step_data.get("status") == "completed":
            return JSONResponse(content=next_step_data)

        return CurrentStepResponse(**next_step_data)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to complete step: {str(e)}"
        )


@router.post("/{session_id}/previous-step", response_model=CurrentStepResponse, response_model_exclude_none=True)
async def go_to_previous_step(
    session_id: uuid.UUID,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    session_service: SessionService = Depends(get_session_service)
):
    """Go back to the previous step if allowed.

    Allows users to review or redo previous steps.
    """
    try:
        # Verify session belongs to current user
        session = await session_service.get_session_simple(session_id, db)

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found"
            )

        if session.user_id != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this session"
            )

        # Go back to previous step
        previous_step_data = await StepDisclosureService.go_back_to_previous_step(
            session_id, db
        )

        return CurrentStepResponse(**previous_step_data)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to go to previous step: {str(e)}"
        )


@router.get("/{session_id}/progress")
async def get_session_progress(
    session_id: uuid.UUID,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    session_service: SessionService = Depends(get_session_service)
):
    """Get overall progress for a guide session.

    Returns high-level progress information without revealing future steps.
    """
    try:
        # Verify session belongs to current user
        session = await session_service.get_session_simple(session_id, db)

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found"
            )

        if session.user_id != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this session"
            )

        # Get current step data which includes progress
        current_data = await StepDisclosureService.get_current_step_only(
            session_id, db
        )

        # Return just the progress information
        return {
            "session_id": str(session_id),
            "guide_title": current_data.get("guide_title", ""),
            "status": current_data.get("status", ""),
            "progress": current_data.get("progress", {}),
            "current_section": {
                "title": current_data.get("current_section", {}).get("section_title", ""),
                "progress": current_data.get("current_section", {}).get("section_progress", {})
            }
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get progress: {str(e)}"
        )


@router.get("/{session_id}/sections/{section_id}/overview")
async def get_section_overview(
    session_id: uuid.UUID,
    section_id: str,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    session_service: SessionService = Depends(get_session_service)
):
    """Get overview of a specific section with step titles (but not full details).

    Allows users to see what's coming in a section without overwhelming them.
    """
    try:
        # Verify session belongs to current user
        session = await session_service.get_session_simple(session_id, db)

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found"
            )

        if session.user_id != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this session"
            )

        # Get section overview
        section_overview = await StepDisclosureService.get_section_overview(
            session_id, section_id, db
        )

        return section_overview

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get section overview: {str(e)}"
        )


@router.post("/{session_id}/request-help")
async def request_step_help(
    session_id: uuid.UUID,
    help_request: dict,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    session_service: SessionService = Depends(get_session_service)
):
    """Request additional help for current step.

    This could trigger additional assistance, hints, or escalation.
    """
    try:
        # Verify session belongs to current user
        session = await session_service.get_session_simple(session_id, db)

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found"
            )

        if session.user_id != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this session"
            )

        # For now, just return the current step with additional hints
        current_data = await StepDisclosureService.get_current_step_only(
            session_id, db
        )

        # Could enhance this to provide additional help or escalate
        return {
            "session_id": str(session_id),
            "help_provided": True,
            "current_step": current_data.get("current_step", {}),
            "additional_hints": [
                "Try breaking this step into smaller parts",
                "Check if you have all required permissions",
                "Refer to the visual markers for guidance",
                "Take a short break if you're feeling stuck"
            ],
            "message": "Additional help has been provided. If you're still stuck, consider going back to review previous steps."
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to provide help: {str(e)}"
        )


@router.post(
    "/{session_id}/report-impossible-step",
    status_code=200,
    responses={
        200: {
            "description": "Alternative steps generated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "status": "adapted",
                        "message": "Generated 2 alternative approaches to work around the blocked step",
                        "blocked_step": {
                            "identifier": "3",
                            "title": "Click the 'Deploy' button",
                            "status": "blocked",
                            "show_as": "crossed_out",
                            "blocked_reason": "UI changed - button doesn't exist"
                        },
                        "alternative_steps": [
                            {
                                "identifier": "3-alt-1",
                                "title": "Use command-line deployment",
                                "description": "Deploy using the Vercel CLI instead of the web UI",
                                "completion_criteria": "App deployed successfully via CLI",
                                "estimated_duration_minutes": 5
                            },
                            {
                                "identifier": "3-alt-2",
                                "title": "Use GitHub integration",
                                "description": "Set up automatic deployments via GitHub",
                                "completion_criteria": "GitHub integration configured",
                                "estimated_duration_minutes": 10
                            }
                        ],
                        "current_step": {
                            "identifier": "3-alt-1",
                            "title": "Use command-line deployment",
                            "description": "Deploy using the Vercel CLI instead of the web UI",
                            "completion_criteria": "App deployed successfully via CLI",
                            "assistance_hints": ["Run 'vercel --prod' in your project"],
                            "visual_markers": []
                        }
                    }
                }
            }
        },
        404: {
            "description": "Session not found"
        },
        403: {
            "description": "Access denied to session"
        },
        500: {
            "description": "Failed to generate alternatives"
        }
    },
    summary="Report impossible step and generate alternative approaches"
)
async def report_impossible_step(
    session_id: uuid.UUID,
    request: StepCompletionRequest,  # Reusing for problem_description in completion_notes
    current_user: UserModel = Depends(get_current_user),
    llm_service = Depends(get_llm_service),
    db: AsyncSession = Depends(get_db),
    session_service: SessionService = Depends(get_session_service)
):
    """
    Report that current step is impossible and request alternative approaches.

    This endpoint enables adaptive guide generation when users encounter blockers.
    When a step becomes impossible to complete (UI changed, feature missing, etc.),
    the system uses an LLM to generate 2-3 alternative approaches.

    ## How It Works

    1. Gathers context about what was completed and what's blocked
    2. Uses LLM to generate 2-3 alternative approaches to achieve the same goal
    3. Updates the guide structure by inserting alternative steps
    4. Marks the original step as blocked (shown with strikethrough in UI)
    5. Advances session to the first alternative step

    ## Common Use Cases

    - UI has changed and button/feature doesn't exist
    - Software version doesn't support the documented approach
    - User's environment differs from guide assumptions
    - API or service endpoint has changed

    ## Example Request

    ```json
    {
      "completion_notes": "The 'Deploy' button doesn't exist in the UI anymore",
      "encountered_issues": "I see 'New Deployment' and 'Import Project' buttons instead",
      "time_taken_minutes": null
    }
    ```

    ## Example Response

    ```json
    {
      "status": "adapted",
      "message": "Generated 2 alternative approaches to work around the blocked step",
      "blocked_step": {
        "identifier": "3",
        "title": "Click the 'Deploy' button",
        "status": "blocked",
        "show_as": "crossed_out",
        "blocked_reason": "UI changed - button doesn't exist"
      },
      "alternative_steps": [
        {
          "identifier": "3-alt-1",
          "title": "Use command-line deployment",
          "description": "Deploy using the Vercel CLI instead",
          "completion_criteria": "App deployed successfully via CLI",
          "estimated_duration_minutes": 5
        },
        {
          "identifier": "3-alt-2",
          "title": "Use GitHub integration",
          "description": "Set up automatic deployments",
          "completion_criteria": "GitHub integration configured",
          "estimated_duration_minutes": 10
        }
      ],
      "current_step": {
        "identifier": "3-alt-1",
        "title": "Use command-line deployment",
        "description": "Deploy using the Vercel CLI instead of the web UI",
        "assistance_hints": ["Run 'vercel --prod' in your project"],
        "completion_criteria": "App deployed successfully via CLI"
      }
    }
    ```

    ## Parameters

    - **completion_notes**: Description of why the step is impossible (required)
    - **encountered_issues**: What the user actually sees in their environment
    - **time_taken_minutes**: Not used for this endpoint

    ## Error Responses

    - **404**: Session not found
    - **403**: User doesn't own this session
    - **500**: Failed to generate alternative steps (LLM error)

    ## Notes

    The blocked step remains in the guide (shown with strikethrough) for transparency.
    Users can see what didn't work and why an alternative approach was needed.
    """
    try:
        # Verify session belongs to current user
        session = await session_service.get_session_simple(session_id, db)

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found"
            )

        if session.user_id != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this session"
            )

        # 1. Check user quota before generating alternatives
        usage_service = UsageService(db)
        daily_budget, monthly_budget = get_user_budgets(current_user.tier)

        can_proceed, error_message = await usage_service.check_limits(
            user_id=current_user.user_id,
            daily_budget=daily_budget,
            monthly_budget=monthly_budget
        )

        if not can_proceed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Usage quota exceeded: {error_message}"
            )

        # Extract problem information from request
        problem_description = request.completion_notes or "Step is impossible to complete"
        what_user_sees = request.encountered_issues or "UI or functionality has changed"

        # Import and use guide adaptation service
        from ..services.guide_adaptation_service import GuideAdaptationService

        adaptation_service = GuideAdaptationService(llm_service)

        # Handle the impossible step and generate alternatives
        result = await adaptation_service.handle_impossible_step(
            session_id=session_id,
            problem_description=problem_description,
            reason="ui_changed",  # Default reason
            what_user_sees=what_user_sees,
            attempted_solutions=[],
            db=db
        )

        # 2. Calculate cost and increment usage for adaptation
        # TODO: Get actual token counts from LLM response
        # For now, use placeholder values: ~1000 tokens input, ~1500 tokens output
        cost_calculator = CostCalculator()
        estimated_cost = cost_calculator.calculate_cost(
            model="claude-3-sonnet",  # TODO: Get actual model from llm_service
            prompt_tokens=1000,
            completion_tokens=1500
        )

        # Increment user usage with estimated cost
        await usage_service.increment_usage(
            user_id=current_user.user_id,
            cost=estimated_cost
        )

        return {
            "status": result["status"],
            "message": result["message"],
            "blocked_step": {
                "identifier": result["blocked_step"].get("step_identifier"),
                "title": result["blocked_step"].get("title"),
                "status": "blocked",
                "show_as": "crossed_out",
                "blocked_reason": result["blocked_step"].get("blocked_reason")
            },
            "alternative_steps": [
                {
                    "identifier": step.get("step_identifier"),
                    "title": step.get("title"),
                    "description": step.get("description"),
                    "completion_criteria": step.get("completion_criteria"),
                    "estimated_duration_minutes": step.get("estimated_duration_minutes")
                }
                for step in result["alternative_steps"]
            ],
            "current_step": {
                "identifier": result["current_step"].get("step_identifier"),
                "title": result["current_step"].get("title"),
                "description": result["current_step"].get("description"),
                "completion_criteria": result["current_step"].get("completion_criteria"),
                "assistance_hints": result["current_step"].get("assistance_hints"),
                "visual_markers": result["current_step"].get("visual_markers")
            }
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate alternative steps: {str(e)}"
        )
