"""add missing segment columns

Revision ID: d3b1029c8e9f
Revises: 9c09b48931b7
Create Date: 2026-06-20 00:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d3b1029c8e9f"
down_revision: Union[str, Sequence[str], None] = "9c09b48931b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("segments", sa.Column("needs_retranslation", sa.Boolean(), server_default="false", nullable=True))
    op.add_column("segments", sa.Column("actual_speed_factor", sa.Float(), server_default="1.0", nullable=True))
    op.add_column("segments", sa.Column("confidence_score", sa.Integer(), server_default="5", nullable=True))


def downgrade() -> None:
    op.drop_column("segments", "confidence_score")
    op.drop_column("segments", "actual_speed_factor")
    op.drop_column("segments", "needs_retranslation")
