"""Add topup_notify_chat_ids to notification_settings

Adds:
- notification_settings.topup_notify_chat_ids (Text, nullable): JSON-encoded
  list of canonical "chat_id" / "chat_id:thread_id" entries used as the
  separate destination for BALANCE_TOPUP_PAID notifications. When NULL/empty,
  the bot falls back to order_notify_whitelist_chat_ids.

Revision ID: d5a8e1c2b9f0
Revises: 4d5966317fb6
Create Date: 2026-05-20 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "d5a8e1c2b9f0"
down_revision = "4d5966317fb6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "notification_settings",
        sa.Column("topup_notify_chat_ids", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("notification_settings", "topup_notify_chat_ids")
