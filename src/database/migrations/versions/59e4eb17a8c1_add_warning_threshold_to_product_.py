"""Add warning threshold to product variations

Revision ID: 59e4eb17a8c1
Revises: d0e1f2a3b4c5
Create Date: 2026-05-18 16:35:15.914676

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '59e4eb17a8c1'
down_revision = 'd0e1f2a3b4c5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('product_variations', sa.Column('warning_threshold_value', sa.Integer(), nullable=True))
    op.add_column('product_variations', sa.Column('warning_threshold_unit', sa.String(length=10), nullable=True))


def downgrade() -> None:
    op.drop_column('product_variations', 'warning_threshold_unit')
    op.drop_column('product_variations', 'warning_threshold_value')
