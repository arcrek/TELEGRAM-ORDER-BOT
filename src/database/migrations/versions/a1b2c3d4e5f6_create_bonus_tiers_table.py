"""Create bonus_tiers table

Revision ID: a1b2c3d4e5f6
Revises: 9b0c1d2e3f4a
Create Date: 2026-01-31

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '9b0c1d2e3f4a'
branch_labels = None
depends_on = None


def upgrade():
    """Create bonus_tiers table."""
    op.create_table(
        'bonus_tiers',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('variation_id', sa.String(), nullable=False),
        sa.Column('min_quantity', sa.Integer(), nullable=False),
        sa.Column('bonus_quantity', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['variation_id'], ['product_variations.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('variation_id', 'min_quantity', name='uq_variation_min_quantity'),
    )
    
    # Create index for faster lookups by variation_id
    op.create_index('ix_bonus_tiers_variation_id', 'bonus_tiers', ['variation_id'])


def downgrade():
    """Drop bonus_tiers table."""
    op.drop_index('ix_bonus_tiers_variation_id', table_name='bonus_tiers')
    op.drop_table('bonus_tiers')
