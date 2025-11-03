"""add_user_usage_table_for_quota_tracking

Revision ID: bea21284f289
Revises: 50fc9a262337
Create Date: 2025-11-01 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "bea21284f289"
down_revision = "50fc9a262337"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create user_usage table for tracking daily/monthly usage and costs."""
    op.create_table(
        "user_usage",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("daily_cost", sa.Float(), nullable=False),
        sa.Column("daily_requests", sa.Integer(), nullable=False),
        sa.Column("daily_reset_date", sa.DateTime(), nullable=False),
        sa.Column("monthly_cost", sa.Float(), nullable=False),
        sa.Column("monthly_requests", sa.Integer(), nullable=False),
        sa.Column("monthly_reset_date", sa.DateTime(), nullable=False),
        sa.Column("daily_budget_exceeded", sa.Boolean(), nullable=False),
        sa.Column("monthly_budget_exceeded", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes for performance
    op.create_index(
        op.f("ix_user_usage_user_id"),
        "user_usage",
        ["user_id"],
        unique=True,
    )


def downgrade() -> None:
    """Drop user_usage table and indexes."""
    op.drop_index(op.f("ix_user_usage_user_id"), table_name="user_usage")
    op.drop_table("user_usage")
