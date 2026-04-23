"""add_direct_on_branch_to_tasks

Revision ID: 1fb2802d0c86
Revises: 6b947996d2bb
Create Date: 2026-03-25 11:13:15.832924

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1fb2802d0c86'
down_revision: Union[str, Sequence[str], None] = '6b947996d2bb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add direct_on_branch column to tasks table."""
    op.add_column('tasks', sa.Column('direct_on_branch', sa.Boolean(), nullable=False, server_default='0'))


def downgrade() -> None:
    """Remove direct_on_branch column from tasks table."""
    op.drop_column('tasks', 'direct_on_branch')
