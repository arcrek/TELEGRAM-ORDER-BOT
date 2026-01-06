"""add payment_message_ids to orders

Revision ID: 6e7f8a9b0c1d
Revises: 5d6e7f8a9b0c
Create Date: 2026-01-06 19:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6e7f8a9b0c1d'
down_revision = '5d6e7f8a9b0c'
branch_labels = None
depends_on = None


def upgrade():
    # Add payment_message_ids column to orders table
    op.add_column('orders', sa.Column('payment_message_ids', sa.Text(), nullable=True))


def downgrade():
    # Remove payment_message_ids column from orders table
    op.drop_column('orders', 'payment_message_ids')

