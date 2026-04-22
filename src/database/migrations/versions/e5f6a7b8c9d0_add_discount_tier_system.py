"""Add discount tier system

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-04-22 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    # 1. Create discount_tiers table
    if "discount_tiers" not in existing_tables:
        op.create_table(
            "discount_tiers",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("variation_id", sa.String(), nullable=False),
            sa.Column("min_quantity", sa.Integer(), nullable=False),
            sa.Column("discount_type", sa.String(), nullable=False),
            sa.Column("discount_value", sa.Integer(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(
                ["variation_id"], ["product_variations.id"], ondelete="CASCADE"
            ),
            sa.UniqueConstraint(
                "variation_id", "min_quantity", name="uq_discount_variation_min_quantity"
            ),
        )
        op.create_index(
            "ix_discount_tiers_variation_id", "discount_tiers", ["variation_id"]
        )

    # 2. Add benefit_mode to product_variations
    variation_columns = [c["name"] for c in inspector.get_columns("product_variations")]
    if "benefit_mode" not in variation_columns:
        op.add_column(
            "product_variations",
            sa.Column("benefit_mode", sa.String(), nullable=False, server_default="bonus"),
        )

    # 3. Add discount_amount to orders
    order_columns = [c["name"] for c in inspector.get_columns("orders")]
    if "discount_amount" not in order_columns:
        op.add_column(
            "orders",
            sa.Column("discount_amount", sa.Integer(), nullable=False, server_default="0"),
        )

    # 4. Add discount_amount to order_items
    order_item_columns = [c["name"] for c in inspector.get_columns("order_items")]
    if "discount_amount" not in order_item_columns:
        op.add_column(
            "order_items",
            sa.Column("discount_amount", sa.Integer(), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    order_item_columns = [c["name"] for c in inspector.get_columns("order_items")]
    if "discount_amount" in order_item_columns:
        op.drop_column("order_items", "discount_amount")

    order_columns = [c["name"] for c in inspector.get_columns("orders")]
    if "discount_amount" in order_columns:
        op.drop_column("orders", "discount_amount")

    variation_columns = [c["name"] for c in inspector.get_columns("product_variations")]
    if "benefit_mode" in variation_columns:
        op.drop_column("product_variations", "benefit_mode")

    if "discount_tiers" in existing_tables:
        op.drop_index("ix_discount_tiers_variation_id", table_name="discount_tiers")
        op.drop_table("discount_tiers")
