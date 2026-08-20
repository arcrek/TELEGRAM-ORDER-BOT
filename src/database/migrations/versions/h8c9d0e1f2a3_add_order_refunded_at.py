"""add order.refunded_at

Revision ID: h8c9d0e1f2a3
Revises: g7b8c9d0e1f2
Create Date: 2026-06-16 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "h8c9d0e1f2a3"
down_revision = "g7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    order_columns = [c["name"] for c in inspector.get_columns("orders")]

    if "refunded_at" not in order_columns:
        op.add_column(
            "orders",
            sa.Column("refunded_at", sa.DateTime(), nullable=True),
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    order_columns = [c["name"] for c in inspector.get_columns("orders")]

    if "refunded_at" in order_columns:
        op.drop_column("orders", "refunded_at")
