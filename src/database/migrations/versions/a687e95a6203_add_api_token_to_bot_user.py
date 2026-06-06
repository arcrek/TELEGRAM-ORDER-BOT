"""add api_token to bot_user

Revision ID: a687e95a6203
Revises: b3c4d5e6f7a8
Create Date: 2026-06-06 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a687e95a6203"
down_revision: Union[str, None] = "b3c4d5e6f7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "bot_users",
        sa.Column("api_token", sa.String(), nullable=True),
    )
    op.create_index(
        "ix_bot_users_api_token",
        "bot_users",
        ["api_token"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_bot_users_api_token", table_name="bot_users")
    op.drop_column("bot_users", "api_token")
