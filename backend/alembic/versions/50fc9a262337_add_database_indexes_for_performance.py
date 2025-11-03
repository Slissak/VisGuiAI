"""add_database_indexes_for_performance

Revision ID: 50fc9a262337
Revises: 2ff9dfb1c619
Create Date: 2025-10-29 10:00:00.000000

This migration adds database indexes to optimize frequently queried columns
and improve query performance across the application.

Indexes added:
- guide_sessions: session_id (already PK), guide_id, user_id (already indexed), status (already indexed), created_at
- step_guides: guide_id (already PK), category, difficulty_level, created_at
- steps: step_id (already PK), guide_id, section_id, step_index, step_status
- completion_events: event_id (already PK), session_id, step_id, completed_at
- progress_trackers: tracker_id (already PK), session_id (already unique), last_activity_at
- sections: section_id (already PK), guide_id, section_order
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "50fc9a262337"
down_revision = "2ff9dfb1c619"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add performance indexes to frequently queried columns."""

    # guide_sessions table indexes
    # user_id and status already have indexes from the model definition
    op.create_index(
        "idx_guide_sessions_guide_id",
        "guide_sessions",
        ["guide_id"],
        unique=False
    )
    op.create_index(
        "idx_guide_sessions_created_at",
        "guide_sessions",
        ["created_at"],
        unique=False
    )
    op.create_index(
        "idx_guide_sessions_user_status",
        "guide_sessions",
        ["user_id", "status"],
        unique=False
    )

    # step_guides table indexes
    op.create_index(
        "idx_step_guides_category",
        "step_guides",
        ["category"],
        unique=False
    )
    op.create_index(
        "idx_step_guides_difficulty_level",
        "step_guides",
        ["difficulty_level"],
        unique=False
    )
    op.create_index(
        "idx_step_guides_created_at",
        "step_guides",
        ["created_at"],
        unique=False
    )

    # steps table indexes
    op.create_index(
        "idx_steps_guide_id",
        "steps",
        ["guide_id"],
        unique=False
    )
    op.create_index(
        "idx_steps_section_id",
        "steps",
        ["section_id"],
        unique=False
    )
    op.create_index(
        "idx_steps_step_status",
        "steps",
        ["step_status"],
        unique=False
    )
    op.create_index(
        "idx_steps_guide_step_index",
        "steps",
        ["guide_id", "step_index"],
        unique=False
    )

    # completion_events table indexes
    op.create_index(
        "idx_completion_events_session_id",
        "completion_events",
        ["session_id"],
        unique=False
    )
    op.create_index(
        "idx_completion_events_step_id",
        "completion_events",
        ["step_id"],
        unique=False
    )
    op.create_index(
        "idx_completion_events_completed_at",
        "completion_events",
        ["completed_at"],
        unique=False
    )

    # progress_trackers table indexes
    op.create_index(
        "idx_progress_trackers_last_activity_at",
        "progress_trackers",
        ["last_activity_at"],
        unique=False
    )

    # sections table indexes
    op.create_index(
        "idx_sections_guide_id",
        "sections",
        ["guide_id"],
        unique=False
    )
    op.create_index(
        "idx_sections_section_order",
        "sections",
        ["section_order"],
        unique=False
    )

    # llm_generation_requests table indexes
    op.create_index(
        "idx_llm_requests_generated_guide_id",
        "llm_generation_requests",
        ["generated_guide_id"],
        unique=False
    )
    op.create_index(
        "idx_llm_requests_created_at",
        "llm_generation_requests",
        ["created_at"],
        unique=False
    )


def downgrade() -> None:
    """Remove performance indexes."""

    # Drop all indexes in reverse order
    op.drop_index("idx_llm_requests_created_at", table_name="llm_generation_requests")
    op.drop_index("idx_llm_requests_generated_guide_id", table_name="llm_generation_requests")

    op.drop_index("idx_sections_section_order", table_name="sections")
    op.drop_index("idx_sections_guide_id", table_name="sections")

    op.drop_index("idx_progress_trackers_last_activity_at", table_name="progress_trackers")

    op.drop_index("idx_completion_events_completed_at", table_name="completion_events")
    op.drop_index("idx_completion_events_step_id", table_name="completion_events")
    op.drop_index("idx_completion_events_session_id", table_name="completion_events")

    op.drop_index("idx_steps_guide_step_index", table_name="steps")
    op.drop_index("idx_steps_step_status", table_name="steps")
    op.drop_index("idx_steps_section_id", table_name="steps")
    op.drop_index("idx_steps_guide_id", table_name="steps")

    op.drop_index("idx_step_guides_created_at", table_name="step_guides")
    op.drop_index("idx_step_guides_difficulty_level", table_name="step_guides")
    op.drop_index("idx_step_guides_category", table_name="step_guides")

    op.drop_index("idx_guide_sessions_user_status", table_name="guide_sessions")
    op.drop_index("idx_guide_sessions_created_at", table_name="guide_sessions")
    op.drop_index("idx_guide_sessions_guide_id", table_name="guide_sessions")
