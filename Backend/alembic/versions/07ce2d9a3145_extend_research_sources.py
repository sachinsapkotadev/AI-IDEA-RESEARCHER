"""extend research sources with content and metadata fields

Revision ID: 07ce2d9a3145
Revises: 06bd93681223
Create Date: 2026-09-21 15:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '07ce2d9a3145'
down_revision: Union[str, Sequence[str], None] = '06bd93681223'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema — extend research_sources table."""
    # Add new columns to research_sources
    op.add_column('research_sources', sa.Column('domain', sa.String(length=200), nullable=True))
    op.add_column('research_sources', sa.Column('snippet', sa.Text(), nullable=True))
    op.add_column('research_sources', sa.Column('content', sa.Text(), nullable=True))
    op.add_column('research_sources', sa.Column('quality', sa.String(length=50), nullable=True))
    op.add_column('research_sources', sa.Column('retrieved_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('research_sources', sa.Column('status', sa.Enum('SUCCESS', 'FAILED', 'SKIPPED', name='source_status'), nullable=False, server_default='success'))
    op.add_column('research_sources', sa.Column('word_count', sa.Integer(), nullable=True))
    op.add_column('research_sources', sa.Column('rank', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema — remove new columns."""
    op.drop_column('research_sources', 'rank')
    op.drop_column('research_sources', 'word_count')
    op.drop_column('research_sources', 'status')
    op.drop_column('research_sources', 'retrieved_at')
    op.drop_column('research_sources', 'quality')
    op.drop_column('research_sources', 'content')
    op.drop_column('research_sources', 'snippet')
    op.drop_column('research_sources', 'domain')
