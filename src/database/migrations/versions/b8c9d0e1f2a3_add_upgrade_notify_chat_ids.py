"""Add upgrade_notify_chat_ids to notification_settings

Adds:
- notification_settings.upgrade_notify_chat_ids (Text, nullable): JSON-encoded
  list of canonical "chat_id" / "chat_id:thread_id" entries used as the
  separate destination for UPGRADE account-info forwarding and the "Done"
  inline button. When NULL/empty, the bot falls back to
  order_notify_whitelist_chat_ids.

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-04-30 00:00:00.000000

"""
import sqlalchemy as sa
from alembic import op

revision = "b8c9d0e1f2a3"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "notification_settings",
        sa.Column("upgrade_notify_chat_ids", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("notification_settings", "upgrade_notify_chat_ids")
