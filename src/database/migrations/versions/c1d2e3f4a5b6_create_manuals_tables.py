"""Create manuals tables

Revision ID: c1d2e3f4a5b6
Revises: a687e95a6203
Create Date: 2026-06-15

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c1d2e3f4a5b6"
down_revision = "a687e95a6203"
branch_labels = None
depends_on = None


def upgrade():
    """Create manuals and manual_product_assignments tables."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if "manuals" not in existing_tables:
        op.create_table(
            "manuals",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("title", sa.String(), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
        )

    if "manual_product_assignments" not in existing_tables:
        op.create_table(
            "manual_product_assignments",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("manual_id", sa.String(), nullable=False),
            sa.Column("product_id", sa.String(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["manual_id"], ["manuals.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["product_id"], ["products.id"], ondelete="CASCADE"
            ),
            sa.UniqueConstraint("manual_id", "product_id", name="uq_manual_product"),
        )
        op.create_index(
            "ix_manual_product_assignments_product_id",
            "manual_product_assignments",
            ["product_id"],
        )


def downgrade():
    """Drop manuals tables."""
    op.drop_index(
        "ix_manual_product_assignments_product_id",
        table_name="manual_product_assignments",
    )
    op.drop_table("manual_product_assignments")
    op.drop_table("manuals")
