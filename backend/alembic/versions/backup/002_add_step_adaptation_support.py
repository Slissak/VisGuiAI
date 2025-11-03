"""Add step adaptation support

Revision ID: 002
Revises: 001
Create Date: 2024-09-29 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create step_status enum
    step_status_enum = postgresql.ENUM('active', 'completed', 'blocked', 'alternative', name='stepstatus')
    step_status_enum.create(op.get_bind(), checkfirst=True)

    # Add adaptation_history and last_adapted_at to step_guides table
    op.add_column('step_guides', sa.Column('adaptation_history', sa.JSON(), nullable=True))
    op.add_column('step_guides', sa.Column('last_adapted_at', sa.DateTime(timezone=True), nullable=True))

    # Add step_identifier, step_status, replaces_step_index, and blocked_reason to steps table
    op.add_column('steps', sa.Column('step_identifier', sa.String(length=10), nullable=False, server_default='0'))
    op.add_column('steps', sa.Column('step_status', step_status_enum, nullable=False, server_default='active'))
    op.add_column('steps', sa.Column('replaces_step_index', sa.Integer(), nullable=True))
    op.add_column('steps', sa.Column('blocked_reason', sa.String(length=500), nullable=True))

    # Change current_step_index to current_step_identifier in guide_sessions table
    # First drop the constraint that references it
    op.drop_constraint('positive_step_index', 'guide_sessions', type_='check')

    # Add new column
    op.add_column('guide_sessions', sa.Column('current_step_identifier', sa.String(length=10), nullable=False, server_default='0'))

    # Copy data from old column to new column (convert int to string)
    op.execute("UPDATE guide_sessions SET current_step_identifier = CAST(current_step_index AS VARCHAR)")

    # Drop old column
    op.drop_column('guide_sessions', 'current_step_index')


def downgrade() -> None:
    # Reverse the changes

    # Add back current_step_index column
    op.add_column('guide_sessions', sa.Column('current_step_index', sa.Integer(), nullable=False, server_default=0))

    # Copy data back (convert string to int, using only numeric part)
    op.execute("UPDATE guide_sessions SET current_step_index = CAST(REGEXP_REPLACE(current_step_identifier, '[^0-9]', '', 'g') AS INTEGER)")

    # Drop new column
    op.drop_column('guide_sessions', 'current_step_identifier')

    # Add back the constraint
    op.create_check_constraint('positive_step_index', 'guide_sessions', 'current_step_index >= 0')

    # Remove columns from steps table
    op.drop_column('steps', 'blocked_reason')
    op.drop_column('steps', 'replaces_step_index')
    op.drop_column('steps', 'step_status')
    op.drop_column('steps', 'step_identifier')

    # Remove columns from step_guides table
    op.drop_column('step_guides', 'last_adapted_at')
    op.drop_column('step_guides', 'adaptation_history')

    # Drop step_status enum
    step_status_enum = postgresql.ENUM('active', 'completed', 'blocked', 'alternative', name='stepstatus')
    step_status_enum.drop(op.get_bind(), checkfirst=True)