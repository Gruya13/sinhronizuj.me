"""make_wiki_rule_user_id_nullable

Revision ID: bce39c06dfe4
Revises: e2b34a6e8f19
Create Date: 2026-06-21 10:46:44.777479

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bce39c06dfe4'
down_revision: Union[str, Sequence[str], None] = 'e2b34a6e8f19'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


import backend

def upgrade() -> None:
    op.alter_column('wiki_rules', 'user_id',
               existing_type=backend.core.models.GUID(),
               nullable=True)


def downgrade() -> None:
    op.alter_column('wiki_rules', 'user_id',
               existing_type=backend.core.models.GUID(),
               nullable=False)
