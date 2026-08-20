"""Add reservation columns to pre_uploaded_products

Prevents overselling race condition: when a QR payment is created, specific
pre-uploaded product rows are reserved for that order. Concurrent orders cannot
claim the same rows. Reservation is released on order cancellation.

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-05-22 00:00:00.000000

"""
import sqlalchemy as sa
from alembic import op

revision = "b3c4d5e6f7a8"
down_revision = "a2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pre_uploaded_products",
        sa.Column("reserved_by_order_id", sa.String(), nullable=True),
    )
    op.add_column(
        "pre_uploaded_products",
        sa.Column("reserved_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_pre_uploaded_products_reserved_by_order_id",
        "pre_uploaded_products",
        ["reserved_by_order_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_pre_uploaded_products_reserved_by_order_id",
        table_name="pre_uploaded_products",
    )
    op.drop_column("pre_uploaded_products", "reserved_at")
    op.drop_column("pre_uploaded_products", "reserved_by_order_id")
