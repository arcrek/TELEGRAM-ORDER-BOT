"""make order_items foreign keys nullable

Revision ID: 2a3b4c5d6e7f
Revises: 142d667a84ac
Create Date: 2025-01-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2a3b4c5d6e7f'
down_revision = '142d667a84ac'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite doesn't support ALTER COLUMN, so we need to recreate the table
    # Make product_id and variation_id nullable in order_items table
    # This allows products and variations to be deleted while preserving order history
    
    # Create new table with nullable columns
    op.create_table('order_items_new',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('order_id', sa.String(), nullable=False),
        sa.Column('product_id', sa.String(), nullable=True),  # Now nullable
        sa.Column('variation_id', sa.String(), nullable=True),  # Now nullable
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('unit_price', sa.Integer(), nullable=False),
        sa.Column('subtotal', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ),
        sa.ForeignKeyConstraint(['variation_id'], ['product_variations.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Copy data from old table to new table
    op.execute(
        "INSERT INTO order_items_new (id, order_id, product_id, variation_id, quantity, unit_price, subtotal) "
        "SELECT id, order_id, product_id, variation_id, quantity, unit_price, subtotal FROM order_items"
    )
    
    # Drop old table
    op.drop_table('order_items')
    
    # Rename new table to original name
    op.rename_table('order_items_new', 'order_items')


def downgrade() -> None:
    # Revert to NOT NULL by recreating table with NOT NULL constraints
    # Note: This will fail if there are NULL values in product_id or variation_id
    
    # Create new table with NOT NULL columns
    op.create_table('order_items_new',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('order_id', sa.String(), nullable=False),
        sa.Column('product_id', sa.String(), nullable=False),  # NOT NULL
        sa.Column('variation_id', sa.String(), nullable=False),  # NOT NULL
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('unit_price', sa.Integer(), nullable=False),
        sa.Column('subtotal', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ),
        sa.ForeignKeyConstraint(['variation_id'], ['product_variations.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Copy data from old table to new table (excluding rows with NULL values)
    op.execute(
        "INSERT INTO order_items_new (id, order_id, product_id, variation_id, quantity, unit_price, subtotal) "
        "SELECT id, order_id, product_id, variation_id, quantity, unit_price, subtotal "
        "FROM order_items WHERE product_id IS NOT NULL AND variation_id IS NOT NULL"
    )
    
    # Drop old table
    op.drop_table('order_items')
    
    # Rename new table to original name
    op.rename_table('order_items_new', 'order_items')

