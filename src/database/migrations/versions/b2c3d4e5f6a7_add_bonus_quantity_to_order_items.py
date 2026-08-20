"""Add bonus_quantity to order_items

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-01-31

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    """Add bonus_quantity column to order_items table."""
    op.add_column(
        'order_items',
        sa.Column('bonus_quantity', sa.Integer(), nullable=False, server_default='0')
    )


def downgrade():
    """Remove bonus_quantity column from order_items table."""
    op.drop_column('order_items', 'bonus_quantity')
