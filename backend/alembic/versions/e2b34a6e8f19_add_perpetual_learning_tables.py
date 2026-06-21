"""add perpetual learning tables

Revision ID: e2b34a6e8f19
Revises: 9d45a91db31f
Create Date: 2026-06-21 10:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import backend


# revision identifiers, used by Alembic.
revision: str = 'e2b34a6e8f19'
down_revision: Union[str, Sequence[str], None] = '34dd9d2d9e65'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add auto_approved to translation_memory
    op.add_column('translation_memory', sa.Column('auto_approved', sa.Boolean(), server_default='false', nullable=True))
    
    # 2. Add qe_score to segments
    op.add_column('segments', sa.Column('qe_score', sa.Float(), nullable=True))
    
    # 3. Create pending_translation_memory table
    op.create_table('pending_translation_memory',
        sa.Column('id', backend.core.models.GUID(), nullable=False),
        sa.Column('user_id', backend.core.models.GUID(), nullable=False),
        sa.Column('project_id', backend.core.models.GUID(), nullable=True),
        sa.Column('source_text', sa.String(), nullable=False),
        sa.Column('target_text', sa.String(), nullable=False),
        sa.Column('occurrence_count', sa.Integer(), server_default='1', nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('pending_translation_memory')
    op.drop_column('segments', 'qe_score')
    op.drop_column('translation_memory', 'auto_approved')
