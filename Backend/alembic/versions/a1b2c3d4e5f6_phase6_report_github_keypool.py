"""Phase 6: report tracking, github integration, key pool tracking

Revision ID: a1b2c3d4e5f6
Revises: 07ce2d9a3145
Create Date: 2026-09-21 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '07ce2d9a3145'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema — Phase 6 additions."""

    # 1. Add provider_key_slot to agent_runs
    op.add_column('agent_runs', sa.Column('provider_key_slot', sa.String(length=10), nullable=True))

    # 2. Add report tracking fields to research_runs
    op.add_column('research_runs', sa.Column('report_status', sa.Enum('PENDING', 'GENERATING', 'COMPLETED', 'FAILED', name='report_status'), nullable=True))
    op.add_column('research_runs', sa.Column('report_generated_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('research_runs', sa.Column('report_error', sa.Text(), nullable=True))

    # 3. Create research_github table
    op.create_table('research_github',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('research_run_id', sa.Integer(), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('owner', sa.String(length=200), nullable=False),
        sa.Column('repository', sa.String(length=200), nullable=False),
        sa.Column('branch', sa.String(length=200), nullable=False),
        sa.Column('file_path', sa.Text(), nullable=False),
        sa.Column('commit_sha', sa.String(length=40), nullable=True),
        sa.Column('commit_url', sa.Text(), nullable=True),
        sa.Column('status', sa.Enum('PENDING', 'PUBLISHING', 'COMPLETED', 'FAILED', name='github_publish_status'), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['research_run_id'], ['research_runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_research_github_research_run_id'), 'research_github', ['research_run_id'], unique=False)
    op.create_index(op.f('ix_research_github_status'), 'research_github', ['status'], unique=False)


def downgrade() -> None:
    """Downgrade schema — Phase 6 rollback."""

    # Drop research_github table
    op.drop_index(op.f('ix_research_github_status'), table_name='research_github')
    op.drop_index(op.f('ix_research_github_research_run_id'), table_name='research_github')
    op.drop_table('research_github')

    # Drop report tracking fields from research_runs
    op.drop_column('research_runs', 'report_error')
    op.drop_column('research_runs', 'report_generated_at')
    op.drop_column('research_runs', 'report_status')

    # Drop provider_key_slot from agent_runs
    op.drop_column('agent_runs', 'provider_key_slot')
