"""Add UPGRADE delivery type

Adds:
- products.upgrade_request_text (Text, nullable): per-product configurable prompt
  shown to the customer to request their account info for upgrade-type orders.
- orders.awaiting_upgrade_info (Boolean, default False): flag flipped True when
  the IPN processor asks the customer for account info; cleared by the bot once
  the customer replies and the message is forwarded to the notification chat.
- orders.upgrade_forwards (Text, nullable): JSON list of message IDs the bot
  posted in each notification chat for this order, used to map admin replies
  back to the originating order so the bot can relay updates to the customer.

DeliveryType enum is stored as a varchar (native_enum=False), so adding the new
"upgrade" value requires no DB-level alteration — the enum type lives in app code.

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-04-29 00:00:00.000000

"""
import sqlalchemy as sa
from alembic import op

revision = "a7b8c9d0e1f2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column("upgrade_request_text", sa.Text(), nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column(
            "awaiting_upgrade_info",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "orders",
        sa.Column("upgrade_forwards", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("orders", "upgrade_forwards")
    op.drop_column("orders", "awaiting_upgrade_info")
    op.drop_column("products", "upgrade_request_text")
