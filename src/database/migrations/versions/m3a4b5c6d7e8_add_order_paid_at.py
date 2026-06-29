"""add order paid_at

Revision ID: m3a4b5c6d7e8
Revises: k1f2a3b4c5d6
Create Date: 2026-06-29
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "m3a4b5c6d7e8"
down_revision: Union[str, None] = "k1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("paid_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "paid_at")
