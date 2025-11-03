"""add_users_table_for_authentication

Revision ID: 05cd0c5ac23c
Revises: bea21284f289
Create Date: 2025-11-01 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "05cd0c5ac23c"
down_revision = "bea21284f289"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create users table for authentication and tier management."""

    # Create UserTier enum type
    user_tier_enum = postgresql.ENUM(
        'free', 'basic', 'professional', 'enterprise',
        name='usertier',
        create_type=True
    )

    # Create users table
    op.create_table(
        "users",
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("tier", sa.String(), nullable=False, server_default="free"),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verification_token", sa.String(length=255), nullable=True),
        sa.Column("verification_token_expires", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reset_token", sa.String(length=255), nullable=True),
        sa.Column("reset_token_expires", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("user_id"),
    )

    # Create indexes for performance
    op.create_index(
        op.f("ix_users_user_id"),
        "users",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_users_email"),
        "users",
        ["email"],
        unique=True,
    )

    # Now that users table exists, add foreign key to user_usage table
    op.create_foreign_key(
        "fk_user_usage_user_id",
        "user_usage",
        "users",
        ["user_id"],
        ["user_id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    """Drop users table and foreign key."""

    # Drop foreign key from user_usage first
    op.drop_constraint("fk_user_usage_user_id", "user_usage", type_="foreignkey")

    # Drop indexes
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_index(op.f("ix_users_user_id"), table_name="users")

    # Drop users table
    op.drop_table("users")

    # Drop UserTier enum type
    op.execute("DROP TYPE IF EXISTS usertier")
