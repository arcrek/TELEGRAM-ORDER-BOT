"""add payos_qr_code to orders and topup_orders

Revision ID: a2b3c4d5e6f7
Revises: f6a7b8c9d0e1
Create Date: 2026-05-22

"""
from alembic import op
import sqlalchemy as sa

revision = "a2b3c4d5e6f7"
down_revision = "d5a8e1c2b9f0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("payos_qr_code", sa.Text(), nullable=True))
    op.add_column("topup_orders", sa.Column("payos_qr_code", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "payos_qr_code")
    op.drop_column("topup_orders", "payos_qr_code")
