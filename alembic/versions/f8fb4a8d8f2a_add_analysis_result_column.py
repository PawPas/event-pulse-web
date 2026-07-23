"""add analysis result column

Revision ID: f8fb4a8d8f2a
Revises: 26aaf8bb5019
Create Date: 2026-07-23 12:45:11.833356

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = 'f8fb4a8d8f2a'
down_revision: Union[str, Sequence[str], None] = '26aaf8bb5019'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('reports', sa.Column('analysis_result', JSONB(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('reports', 'analysis_result')
