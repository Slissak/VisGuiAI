"""recreate_all_tables

Revision ID: 2ff9dfb1c619
Revises: 23cf83858f53
Create Date: 2025-10-18 22:58:22.321287

"""

from alembic import op
import sqlalchemy as sa
from src.models.database import Base


# revision identifiers, used by Alembic.
revision = "2ff9dfb1c619"
down_revision = "23cf83858f53"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind)
    Base.metadata.create_all(bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind)
    Base.metadata.create_all(bind)
