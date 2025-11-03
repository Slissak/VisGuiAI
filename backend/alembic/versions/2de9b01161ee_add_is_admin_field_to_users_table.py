"""add_is_admin_field_to_users_table

Revision ID: 2de9b01161ee
Revises: 05cd0c5ac23c
Create Date: 2025-11-03 10:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2de9b01161ee'
down_revision: Union[str, None] = '05cd0c5ac23c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add is_admin field to users table."""
    op.add_column('users', sa.Column('is_admin', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    """Remove is_admin field from users table."""
    op.drop_column('users', 'is_admin')
