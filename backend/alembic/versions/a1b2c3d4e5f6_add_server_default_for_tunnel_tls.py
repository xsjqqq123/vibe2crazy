"""add server default for tunnel tls columns

Revision ID: a1b2c3d4e5f6
Revises: 80f2583432cf
Create Date: 2026-04-25 13:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '80f2583432cf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Set server defaults and fix existing NULL/0 values."""
    # Fix existing rows where use_tls is NULL or 0
    op.execute("UPDATE tunnel_config SET use_tls = 1 WHERE use_tls IS NULL OR use_tls = 0")
    # Note: SQLite doesn't support ALTER COLUMN to add server_default,
    # but the code-level defaults in tunnel_service.py handle NULL values.


def downgrade() -> None:
    """No-op: reverting defaults is not needed."""
    pass
