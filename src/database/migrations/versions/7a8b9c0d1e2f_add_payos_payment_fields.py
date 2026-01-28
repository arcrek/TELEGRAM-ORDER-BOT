"""add payos payment fields to orders

Revision ID: 7a8b9c0d1e2f
Revises: 6e7f8a9b0c1d
Create Date: 2026-01-28 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "7a8b9c0d1e2f"
down_revision = "6e7f8a9b0c1d"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("orders", sa.Column("payment_provider", sa.String(), nullable=True))
    op.add_column("orders", sa.Column("payos_order_code", sa.BigInteger(), nullable=True))
    op.add_column("orders", sa.Column("payos_payment_link_id", sa.String(), nullable=True))
    op.add_column("orders", sa.Column("payos_checkout_url", sa.Text(), nullable=True))

    # Unique orderCode for PayOS reconciliation
    op.create_index(
        "ix_orders_payos_order_code",
        "orders",
        ["payos_order_code"],
        unique=True,
    )


def downgrade():
    op.drop_index("ix_orders_payos_order_code", table_name="orders")
    op.drop_column("orders", "payos_checkout_url")
    op.drop_column("orders", "payos_payment_link_id")
    op.drop_column("orders", "payos_order_code")
    op.drop_column("orders", "payment_provider")

