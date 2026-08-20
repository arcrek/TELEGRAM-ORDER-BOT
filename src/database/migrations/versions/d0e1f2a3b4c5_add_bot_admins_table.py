"""Add bot_admins table

Stores Telegram user IDs that have bot-admin privileges (can use
/notify_*, the upgrade Done button, etc.). Replaces the file-based
config/bot_admins.json which was not persisted across Docker rebuilds.

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-04-30 00:00:00.000000

"""
import sqlalchemy as sa
from alembic import op

revision = "d0e1f2a3b4c5"
down_revision = "c9d0e1f2a3b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bot_admins",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("added_by", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("telegram_user_id"),
    )
    op.create_index(
        "ix_bot_admins_telegram_user_id",
        "bot_admins",
        ["telegram_user_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_bot_admins_telegram_user_id", table_name="bot_admins")
    op.drop_table("bot_admins")
