"""Add upgrade_prompt_msg_id to orders

Adds:
- orders.upgrade_prompt_msg_id (BigInteger, nullable): Telegram message ID of the
  account-info prompt sent to the customer after payment. Stored so that subsequent
  customer replies to that specific message are forwarded to the admin channel even
  after awaiting_upgrade_info has been cleared.

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-04-30 00:00:00.000000

"""
import sqlalchemy as sa
from alembic import op

revision = "c9d0e1f2a3b4"
down_revision = "b8c9d0e1f2a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column("upgrade_prompt_msg_id", sa.BigInteger(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("orders", "upgrade_prompt_msg_id")
